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

    gemini_api_key = os.getenv('API_KEY')
    elevenlabs_api_key = os.getenv("XI_API_KEY")
    spanish_voice_id = os.getenv('SPANISH_VOICE_ID')
    tavily_api_key = os.getenv("TAVILY_API_KEY")
    suno_api_key = os.getenv("SUNO_API_KEY")
    embedding_model = os.getenv("EMBEDDING_MODEL")
    llm_model = os.getenv("LLM_MODEL")
    image_model = os.getenv("IMAGE_MODEL")
    suno_model = os.getenv("SUNO_MODEL")

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
    suno_adapter = SunoMusicAdapter(suno_api_key, suno_model)

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
    st.session_state.final_selections = {}
if 'corner_selections' not in st.session_state:
    st.session_state.corner_selections = {}
if 'current_topic_idx' not in st.session_state:
    st.session_state.current_topic_idx = 0


def reset():
    st.session_state.clear()
    st.rerun()


st.set_page_config(page_title="Multimodal Video Studio", layout="wide")
st.title("🎬 Multi-Topic Studio")

# ==========================================
# STEP 1: GENERATE & SELECT TOPICS
# ==========================================
if st.session_state.step == 1:
    st.header("Step 1: Discover & Select Topics")

    col1, col2 = st.columns(2)
    with col1:
        # --- NEW: Added 'Bring Your Own Images' to the strategy list ---
        strategy = st.radio("Strategy:",
                            ["AI Trending (Tavily)", "Random Roulette", "Manual Override", "Bring Your Own Images"])

        if strategy != "Bring Your Own Images":
            limit = st.slider("Max topics to fetch", 1, 10, 5)
            manual_topics = st.text_input("Manual Topics (comma separated, if override):", "Disciplina, Fuerza")

    # ==========================================
    # BRANCH A: MANUAL IMAGE UPLOAD
    # ==========================================
    if strategy == "Bring Your Own Images":
        st.markdown("---")
        st.subheader("📸 Upload Your Visuals")
        uploaded_files = st.file_uploader("Upload 9:16 portrait images (PNG/JPG)", accept_multiple_files=True,
                                          type=['png', 'jpg', 'jpeg'])

        if uploaded_files:
            st.markdown("### Configure Uploaded Images")
            manual_configs = []

            # Display a mini-dashboard to configure each uploaded image
            for idx, uf in enumerate(uploaded_files):
                col_img, col_cfg = st.columns([1, 3])
                with col_img:
                    st.image(uf, width=150)
                with col_cfg:
                    t_name = st.text_input(f"Topic Name for Image {idx + 1}", key=f"man_top_{idx}")
                    c_choice = st.selectbox(f"Start Corner for Image {idx + 1}", ["BR", "BL", "TR", "TL", "CR", "CD"],
                                            format_func=lambda x:
                                            {"BR": "Bottom Right", "BL": "Bottom Left", "TR": "Top Right",
                                             "TL": "Top Left", "CR": "Center Rise", "CD": "Center Drift"}[x], key=f"man_corn_{idx}")
                    manual_configs.append((uf, t_name, c_choice))
                st.markdown("---")

            if st.button("🚀 Process Uploaded Images (Skip to Render)", type="primary"):
                # 1. Validation to ensure no blank or duplicate topics
                valid = True
                topics_seen = set()
                target_topics = []

                for uf, t, c in manual_configs:
                    safe_topic = t.strip()
                    if not safe_topic:
                        st.error("❌ Please provide a topic name for all images.")
                        valid = False
                        break
                    if safe_topic in topics_seen:
                        st.error(f"❌ Topic '{safe_topic}' is duplicated. Topics must be unique.")
                        valid = False
                        break
                    topics_seen.add(safe_topic)
                    target_topics.append(safe_topic)  # Collect topics to query ChromaDB

                if valid:
                    with st.spinner("Fetching brand colors from ChromaDB and preparing pipeline..."):
                        # Clear old state completely
                        st.session_state.my_dict = {}
                        st.session_state.final_selections = {}
                        st.session_state.corner_selections = {}

                        # --- NEW: Ask the orchestrator to fetch the exact topics from ChromaDB ---
                        raw_topics_str = services["orchestrator"].generate_explicit_video_topics(
                            target_topics=target_topics)

                        # Parse the returned string (e.g., "Disciplina: [255, 255, 255]") into a mapping dictionary
                        color_mapping = {}
                        if raw_topics_str:
                            for line in raw_topics_str.split('\n'):
                                if ':' in line:
                                    parts = line.split(':', 1)
                                    topic_name = parts[0].strip()
                                    color_str = parts[1].strip()
                                    color_mapping[topic_name] = color_str

                        # Process each image manually
                        for uf, t, c in manual_configs:
                            safe_topic = t.strip()
                            path = f"data/images/current/{safe_topic}_manual.png"

                            # Save the file bytes directly
                            services["storer"].save(path, uf.getvalue())

                            # --- NEW: Retrieve the specific ChromaDB color, fallback to white if not found ---
                            actual_color = color_mapping.get(safe_topic, "[255, 255, 255]")

                            # Create the dictionary so Step 3 uses the correct font_rgb
                            st.session_state.my_dict[safe_topic] = {"font_rgb": actual_color}
                            st.session_state.final_selections[safe_topic] = path
                            st.session_state.corner_selections[safe_topic] = c

                        # Jump directly to Step 3!
                        st.session_state.step = 3
                        st.rerun()

    # ==========================================
    # BRANCH B: STANDARD AI PIPELINE
    # ==========================================
    else:
        if st.button("🔍 Fetch Topics from Database"):
            # --- FIX: Aggressively clear old state when fetching new topics ---
            st.session_state.pop('raw_topics_str', None)
            st.session_state.pop('my_dict', None)
            st.session_state.pop('topics_to_process', None)
            st.session_state.final_selections = {}
            st.session_state.corner_selections = {}
            st.session_state.current_topic_idx = 0

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

                        prompt_template = services["storer"].retrieve('data/prompts/generate_content.txt').decode(
                            'utf-8')
                        final_prompt = prompt_template.format(topics_color=filtered_topics_str)

                        raw_dict = services["content_generator"].generate(final_prompt)

                        # --- FIX: The Bouncer. Strictly filter out hallucinated topics ---
                        st.session_state.my_dict = {
                            k: v for k, v in raw_dict.items() if k in selected_topic_names
                        }

                        if not st.session_state.my_dict:
                            st.error("Gemini failed to process the specific topics requested. Please try again.")
                        else:
                            st.session_state.topics_to_process = list(st.session_state.my_dict.keys())
                            st.session_state.step = 2
                            st.rerun()

# ==========================================
# STEP 2: BATCH IMAGE GENERATION & GALLERY SELECTION
# ==========================================
elif st.session_state.step == 2:
    st.header("Step 2: Visual Selection Gallery")

    # --- 1. THE BATCH GENERATOR ---
    # We use a progress bar to show the user that we are generating all images upfront.
    if 'images_generated' not in st.session_state:
        st.session_state.images_generated = False

    if not st.session_state.images_generated:
        st.markdown("### 🎨 Batch Generating Images...")
        progress_bar = st.progress(0.0)
        total = len(st.session_state.topics_to_process)

        for idx, topic in enumerate(st.session_state.topics_to_process):
            state_key_1 = f"img1_{topic}"
            state_key_2 = f"img2_{topic}"

            # Only generate if they don't exist yet (allows for targeted regenerations later)
            if state_key_1 not in st.session_state or state_key_2 not in st.session_state:
                with st.spinner(f"Generating 2 concepts for '{topic}'..."):
                    topic_data = st.session_state.my_dict[topic]
                    prompt1 = topic_data['image_prompts'][0]
                    prompt2 = topic_data['image_prompts'][1]

                    path1 = f"data/images/current/{topic}_1.png"
                    path2 = f"data/images/current/{topic}_2.png"

                    st.session_state[state_key_1] = services["image_generator"].generate(prompt1, path1)
                    st.session_state[state_key_2] = services["image_generator"].generate(prompt2, path2)

            progress_bar.progress((idx + 1) / total)

        st.session_state.images_generated = True
        st.rerun()  # Refresh the page to show the gallery

    # --- 2. THE GALLERY DASHBOARD ---
    if st.session_state.images_generated:
        st.success("All images generated! Please make your selections below.")

        # We will collect the user's choices in this dictionary before saving to the final state
        temp_selections = {}

        for topic in st.session_state.topics_to_process:
            st.markdown("---")
            st.subheader(f"Topic: {topic}")

            state_key_1 = f"img1_{topic}"
            state_key_2 = f"img2_{topic}"

            # Create a 3-column layout: Option A | Option B | Controls
            colA, colB, colC = st.columns([1, 1, 1.5])

            with colA:
                st.image(st.session_state[state_key_1], caption="Option A", width=250)
            with colB:
                st.image(st.session_state[state_key_2], caption="Option B", width=250)

            with colC:
                st.markdown("#### Action")
                # Use a radio button for the selection logic
                choice = st.radio(
                    "Select an option for this topic:",
                    ["Option A", "Option B", "Skip this Topic"],
                    key=f"radio_{topic}",
                    index=0
                )
                temp_selections[topic] = choice

                # Targeted Regeneration Button
                if st.button(f"🔄 Regenerate images for {topic}", key=f"regen_{topic}"):
                    del st.session_state[state_key_1]
                    del st.session_state[state_key_2]
                    st.session_state.images_generated = False  # Force the generator loop to run again
                    st.rerun()

        st.markdown("---")

        # --- 3. FINAL CONFIRMATION BUTTON ---
        if st.button("✅ Confirm All Selections & Proceed to Render Settings", type="primary", use_container_width=True):
            # Process the temporary selections into the final state
            st.session_state.final_selections = {}
            st.session_state.corner_selections = {}

            for topic, choice in temp_selections.items():
                if choice == "Option A":
                    st.session_state.final_selections[topic] = st.session_state[f"img1_{topic}"]
                    st.session_state.corner_selections[topic] = "BR"  # Default, can be changed in Step 3
                elif choice == "Option B":
                    st.session_state.final_selections[topic] = st.session_state[f"img2_{topic}"]
                    st.session_state.corner_selections[topic] = "BR"  # Default
                # If "Skip", we just don't add it to final_selections

            st.session_state.step = 3
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
        st.success("All selections complete! Review your batch below.")

        st.markdown("### 📝 Review & Finalize Configurations")

        for topic, img_path in st.session_state.final_selections.items():
            st.markdown("---")
            col_img, col_cfg = st.columns([1, 4])

            with col_img:
                st.image(img_path, width=150)

            with col_cfg:
                st.markdown(f"#### **{topic}**")

                current_corner = st.session_state.corner_selections.get(topic, "BR")
                corner_opts = ["BR", "BL", "TR", "TL", "CR", "CD"]

                new_corner = st.selectbox(
                    f"Start Corner:",
                    options=corner_opts,
                    index=corner_opts.index(current_corner),
                    format_func=lambda x:
                    {"BR": "Bottom Right", "BL": "Bottom Left", "TR": "Top Right", "TL": "Top Left", "CR": "Center Rise", "CD": "Center Drift"}[x],
                    key=f"final_corner_{topic}"
                )

                st.session_state.corner_selections[topic] = new_corner

        st.markdown("---")

        if st.button("🎬 RUN FULL BATCH GENERATION", type="primary", use_container_width=True):
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