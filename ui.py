import os
import io
import dotenv
import PIL.Image
import ftfy
import streamlit as st

# --- IMPORT ADAPTERS & SERVICES ---
from adapters.gemini.gemini_text_adapter import GeminiTextAdapter
from adapters.gemini.gemini_image_adapter import GeminiImageAdapter
from adapters.sunoapi.suno_music_adapter import SunoMusicAdapter
from adapters.local_storage.local_file_storage import LocalFileStorageAdapter
from adapters.elevenlabs.elevenlabs_voice_adapter import ElevenLabsVoiceAdapter
from adapters.video.opencv_moviepy_adapter import OpenCVVideoAdapter
from adapters.image.opencv_image_adapter import OpenCVImageAdapter
from adapters.image.opencv_title_adapter import OpenCVTitleImageAdapter
from adapters.audio.librosa_audio_adapter import LibrosaAudioAdapter
from adapters.search.tavily_adapter import TavilyTrendAdapter
from adapters.database.chroma_topic_adapter import ChromaTopicAdapter
from adapters.embedding.gemini_embedding import ModernGeminiEmbeddingAdapter

from domain.services.content_generator import ContentGeneratorService
from domain.services.image_generator import ImageGenerationService
from domain.services.music_generation import MusicGenerationService
from domain.services.voice_pipeline import VoicePipelineService
from domain.services.video_orchestrator import VideoOrchestratorService
from domain.services.image_overlay_orchestrator import ImageOverlayOrchestratorService
from domain.services.title_orchestrator import TitleImageOrchestratorService
from domain.services.audio_analaysys_orchestrator import AudioAnalysisService
from domain.services.trends_orchestrator import TrendOrchestratorService


# ==========================================
# 1. DEPENDENCY INJECTION (CACHED)
# ==========================================
@st.cache_resource
def load_services():
    dotenv.load_dotenv()

    gemini_api_key = os.getenv('API_KEY_BILLED')
    elevenlabs_api_key = os.getenv("XI_API_KEY")
    spanish_voice_id = os.getenv('SPANISH_VOICE_ID')
    tavily_api_key = os.getenv("TAVILY_API_KEY")
    embedding_model = os.getenv("EMBEDDING_MODEL")
    llm_model = os.getenv("LLM_MODEL")
    image_model = os.getenv("IMAGE_MODEL")

    font = 'font/League_Spartan/static/LeagueSpartan-Bold.ttf'
    logo = 'data/logo/logo.png'

    # Adapters
    video_renderer = OpenCVVideoAdapter(font, logo)
    image_renderer = OpenCVImageAdapter(font)
    title_renderer = OpenCVTitleImageAdapter(font)
    drop_detector = LibrosaAudioAdapter()
    tavily_adapter = TavilyTrendAdapter(tavily_api_key)
    modern_gemini_ef = ModernGeminiEmbeddingAdapter(api_key=gemini_api_key, model_name=embedding_model)
    chroma_adapter = ChromaTopicAdapter(storage_path="./chroma_storage", embedding_function=modern_gemini_ef)
    storer = LocalFileStorageAdapter('.')
    gemini_text_adapter = GeminiTextAdapter(gemini_api_key, llm_model)
    gemini_image_adapter = GeminiImageAdapter(gemini_api_key, image_model)
    voice_adapter = ElevenLabsVoiceAdapter(api_key=elevenlabs_api_key, voice_id=spanish_voice_id)
    suno_adapter = SunoMusicAdapter(os.getenv("SUNO_API_KEY"), "V4_5PLUS")

    # Services
    return {
        "storer": storer,
        "content_generator": ContentGeneratorService(gemini_text_adapter),
        "image_generator": ImageGenerationService(gemini_image_adapter, storer),
        "video_services": VideoOrchestratorService(video_renderer, storer),
        "image_service": ImageOverlayOrchestratorService(image_renderer, storer),
        "title_service": TitleImageOrchestratorService(title_renderer, storer),
        "drop_service": AudioAnalysisService(drop_detector),
        "orchestrator": TrendOrchestratorService(searcher=tavily_adapter, repository=chroma_adapter),
        "voice_service": VoicePipelineService(voice_port=voice_adapter, storage=storer),
        "music_service": MusicGenerationService(suno_adapter, storer)
    }


services = load_services()

# ==========================================
# 2. STATE MACHINE SETUP
# ==========================================
if 'step' not in st.session_state:
    st.session_state.step = 1
if 'final_selections' not in st.session_state:
    st.session_state.final_selections = {}  # Maps topic_name -> selected_image_path
if 'corner_selections' not in st.session_state:
    st.session_state.corner_selections = {}  # Maps topic_name -> starting_corner string
if 'current_topic_idx' not in st.session_state:
    st.session_state.current_topic_idx = 0


def reset():
    st.session_state.clear()
    st.rerun()


st.set_page_config(page_title="Visionary Whispers Studio", layout="wide")
st.title("🎬 Visionary Whispers Multi-Topic Studio")

# ==========================================
# STEP 1: GENERATE & SELECT TOPICS
# ==========================================
if st.session_state.step == 1:
    st.header("Step 1: Discover & Select Topics")

    col1, col2 = st.columns(2)
    with col1:
        strategy = st.radio("Strategy:", ["AI Trending (Tavily)", "Random Roulette", "Manual Override"])
        limit = st.slider("Max topics to fetch", 1, 10, 5)
        manual_topics = st.text_input("Manual Topics (comma separated, if override):", "Disciplina, Fuerza")

    if st.button("🔍 Fetch Topics from Database"):
        with st.spinner("Fetching..."):
            if strategy == "AI Trending (Tavily)":
                raw_topics_str = services["orchestrator"].generate_trending_video_topics(limit=limit)
            elif strategy == "Random Roulette":
                raw_topics_str = services["orchestrator"].generate_random_video_topics(limit=limit)
            else:
                topics_list = [t.strip() for t in manual_topics.split(',')]
                raw_topics_str = services["orchestrator"].generate_explicit_video_topics(target_topics=topics_list)

            st.session_state.raw_topics_str = raw_topics_str
            st.rerun()

    if 'raw_topics_str' in st.session_state:
        st.markdown("---")
        st.subheader("Available Topics Found:")

        topic_lines = [line for line in st.session_state.raw_topics_str.split('\n') if line.strip()]
        topic_names = [line.split(':')[0].strip() for line in topic_lines]

        selected_topic_names = st.multiselect(
            "Select the topics you want to generate videos for today:",
            options=topic_names,
            default=topic_names
        )

        if st.button("🚀 Generate Prompts for Selected Topics", type="primary"):
            if not selected_topic_names:
                st.error("Please select at least one topic.")
            else:
                with st.spinner("Asking Gemini to generate image prompts and colors..."):
                    filtered_lines = [line for line in topic_lines if
                                      line.split(':')[0].strip() in selected_topic_names]
                    filtered_topics_str = "\n".join(filtered_lines)

                    prompt_template = services["storer"].retrieve('data/prompts/generate_content.txt').decode('utf-8')
                    final_prompt = prompt_template.format(topics_color=filtered_topics_str)

                    st.session_state.my_dict = services["content_generator"].generate(final_prompt)
                    st.session_state.topics_to_process = list(st.session_state.my_dict.keys())
                    st.session_state.step = 2
                    st.rerun()

# ==========================================
# STEP 2: IMAGE GENERATION & SELECTION LOOP
# ==========================================
elif st.session_state.step == 2:
    if st.session_state.current_topic_idx >= len(st.session_state.topics_to_process):
        st.session_state.step = 3
        st.rerun()

    current_topic = st.session_state.topics_to_process[st.session_state.current_topic_idx]
    topic_data = st.session_state.my_dict[current_topic]

    st.header(f"Step 2: Visuals for '{current_topic}'")
    st.progress(st.session_state.current_topic_idx / len(st.session_state.topics_to_process))

    state_key_1 = f"img1_{current_topic}"
    state_key_2 = f"img2_{current_topic}"

    if state_key_1 not in st.session_state:
        if st.button(f"🎨 Generate 2 Images for {current_topic}"):
            with st.spinner("Gemini is drawing..."):
                prompt1 = topic_data['image_prompts'][0]
                prompt2 = topic_data['image_prompts'][1]

                path1 = f"data/images/current/{current_topic}_1.png"
                path2 = f"data/images/current/{current_topic}_2.png"

                st.session_state[state_key_1] = services["image_generator"].generate(prompt1, path1)
                st.session_state[state_key_2] = services["image_generator"].generate(prompt2, path2)
                st.rerun()
    else:
        # --- NEW: Corner Configuration ---
        st.subheader("🎥 Video Configuration")
        corner_choice = st.selectbox(
            "Select Ken Burns Starting Corner:",
            options=["BR", "BL", "TR", "TL"],
            format_func=lambda x: {"BR": "Bottom Right", "BL": "Bottom Left", "TR": "Top Right", "TL": "Top Left"}[x],
            key=f"corner_{current_topic}"
        )

        st.markdown("---")
        st.subheader("🖼️ Image Selection")
        col1, col2 = st.columns(2)
        with col1:
            st.image(st.session_state[state_key_1], caption="Option A")
            if st.button("✅ Select Option A", key=f"btnA_{current_topic}", use_container_width=True):
                st.session_state.final_selections[current_topic] = st.session_state[state_key_1]
                st.session_state.corner_selections[current_topic] = corner_choice
                st.session_state.current_topic_idx += 1
                st.rerun()

        with col2:
            st.image(st.session_state[state_key_2], caption="Option B")
            if st.button("✅ Select Option B", key=f"btnB_{current_topic}", use_container_width=True):
                st.session_state.final_selections[current_topic] = st.session_state[state_key_2]
                st.session_state.corner_selections[current_topic] = corner_choice
                st.session_state.current_topic_idx += 1
                st.rerun()

        st.markdown("---")
        st.subheader("🛠️ Overrides")
        col_regen, col_skip = st.columns(2)

        # --- NEW: Regenerate Button ---
        with col_regen:
            if st.button("🔄 Regenerate Images", key=f"regen_{current_topic}"):
                # Delete the current images from state to force a re-generation
                del st.session_state[state_key_1]
                del st.session_state[state_key_2]
                st.rerun()

        # --- NEW: Skip Button ---
        with col_skip:
            if st.button("⏭️ Skip this Topic", type="secondary", key=f"skip_{current_topic}"):
                # Increment counter WITHOUT adding to final_selections
                st.session_state.current_topic_idx += 1
                st.rerun()

# ==========================================
# STEP 3: FINAL PIPELINE EXECUTION
# ==========================================
elif st.session_state.step == 3:
    st.header("Step 3: Render Batch")

    if not st.session_state.final_selections:
        st.warning("You skipped all topics! Nothing to render.")
        if st.button("Start Over"):
            reset()
    else:
        st.success("Images selected! Ready to process the batch.")

        st.write("Topics in queue:")
        for topic, img_path in st.session_state.final_selections.items():
            corner_label = {"BR": "Bottom Right", "BL": "Bottom Left", "TR": "Top Right", "TL": "Top Left"}[
                st.session_state.corner_selections[topic]]
            st.write(f"- **{topic}** (Start Corner: {corner_label})")

        if st.button("🎬 RUN FULL BATCH GENERATION", type="primary"):
            progress_bar = st.progress(0.0)
            total_topics = len(st.session_state.final_selections)

            for idx, (topic, chosen_img_path) in enumerate(st.session_state.final_selections.items()):
                with st.status(f"Processing {topic}... ({idx + 1}/{total_topics})") as status:
                    try:
                        topic_data = st.session_state.my_dict[topic]
                        font_rgb = topic_data['font_rgb']
                        chosen_corner = st.session_state.corner_selections[topic]

                        # 1. Generate Quotes
                        st.write("✍️ Writing quotes from image...")
                        desc_prompt_template = services["storer"].retrieve('data/prompts/generate_quotes.txt').decode(
                            'utf-8')
                        desc_prompt = desc_prompt_template.format(font_rgb=font_rgb, split_quote1='', split_quote2='',
                                                                  topic=topic)

                        raw_image = services["storer"].retrieve(chosen_img_path)
                        pil_img = PIL.Image.open(io.BytesIO(raw_image))
                        my_dict2 = services["content_generator"].generate_from_image(pil_img, desc_prompt)

                        # 2. File Moves & Overlays
                        st.write("🖼️ Applying text overlays & titles...")
                        final_image_path = f"data/images/{my_dict2['image_name']}.png"
                        services["storer"].move(chosen_img_path, final_image_path)

                        text_diff_mult = 2
                        services["image_service"].generate_final_image(
                            my_dict2['image_name'], my_dict2['quotes'], final_image_path,
                            my_dict2['color'], my_dict2['suggested_border_rgb'], text_diff_mult
                        )

                        services["title_service"].generate_title(
                            topic, final_image_path, my_dict2['color'], my_dict2['suggested_border_rgb']
                        )

                        # 3. Audio & Voices
                        st.write("🎙️ Synthesizing voices & music...")
                        voice_path_1, voice_path_2 = services["voice_service"].generate_voices(
                            title=my_dict2['image_name'], quotes=my_dict2['quotes']
                        )

                        music_path = services["music_service"].generate_and_save_track(my_dict2['music'])
                        epic_part = services["drop_service"].get_epic_drop_time(music_path, 16, 6)

                        # 4. Final Video Render
                        st.write("🎬 Rendering Ken Burns Video...")
                        services["video_services"].compile_final_content(
                            my_dict2['image_name'], my_dict2['quotes'], final_image_path, music_path,
                            [voice_path_1, voice_path_2], chosen_corner, my_dict2['suggested_border_rgb'],
                            my_dict2['color'], epic_part, 0.75, 3, 40, 12, text_diff_mult
                        )

                        # 5. Save TikTok description
                        st.write("📝 Formatting TikTok description...")
                        video_desc_bytes = services["storer"].retrieve('videos_descr_esp.txt')
                        video_desc = video_desc_bytes.decode('utf-8')
                        final_desc = ftfy.fix_text(my_dict2['tiktok_description']) + '\n\n' + video_desc

                        services["storer"].save(f"data/videos/{my_dict2['image_name']}_desc.txt",
                                                final_desc.encode('utf-8'))

                        status.update(label=f"✅ {topic} complete!", state="complete")

                    except Exception as e:
                        status.update(label=f"❌ Error processing {topic}: {str(e)}", state="error")

                progress_bar.progress((idx + 1) / total_topics)

            st.success("🎉 ALL VIDEOS GENERATED SUCCESSFULLY!")
            st.balloons()

        if st.button("Start Over"):
            reset()