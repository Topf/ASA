import os
import time
import requests
import math
from runwayml import RunwayML

# Correct imports for the latest versions of the libraries
from elevenlabs.client import ElevenLabs
from elevenlabs import save
from moviepy import *
from mutagen.mp3 import MP3
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()

# --- Configuration ---
# It's recommended to store your API keys in a .env file for security
# Your .env file should look like this:
# RUNWAYML_API_SECRET=your_runwayml_api_key
# ELEVENLABS_API_KEY=your_elevenlabs_api_key

RUNWAYML_API_SECRET = "key_de80f9daecc933e4dee38a834b4ad5345a2ac232bdccd2ec530cb58fe2d8378a2b7ec196743fbdb2c6893f56c83a9107114f8047ec0ab9c52fe3634cd6efc575"
ELEVENLABS_API_KEY = "sk_241963330f418ebe22a57719bb28b1984a38c8839f35dc64"

# --- 1. ElevenLabs Text-to-Audio Generation (Revamped) ---
def generate_audio_from_text(text, filename="generated_audio.mp3"):
    """
    Generates audio from text using the ElevenLabs API and saves it to a file.
    Returns the path to the audio file and its duration in seconds.
    """
    if not ELEVENLABS_API_KEY:
        print("ElevenLabs API key not found.")
        return None, 0

    print("Generating audio from text with ElevenLabs...")
    try:
        # Instantiate the ElevenLabs client with your API key
        client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
        
        # Generate audio using the new client.text_to_speech.convert() method
        # This aligns with the latest ElevenLabs API documentation.
        # The Voice ID for "Rachel" is "21m00Tcm4TlvDq8ikWAM"
        audio = client.text_to_speech.convert(
            text=text,
            voice_id="21m00Tcm4TlvDq8ikWAM",  # Using specific Voice ID for robustness
            model_id="eleven_multilingual_v2", # Using model_id parameter
            output_format="mp3_44100_128"     # Specifying output format
        )

        # Create a directory for audio files
        os.makedirs("generated_audio", exist_ok=True)
        audio_path = os.path.join("generated_audio", filename)

        # The save function works with the raw audio stream from .convert()
        save(audio, audio_path)
        print(f"Audio saved successfully to {audio_path}")

        # Get audio duration
        audio_info = MP3(audio_path)
        duration = audio_info.info.length
        print(f"Audio duration: {duration:.2f} seconds")

        return audio_path, duration
    except Exception as e:
        print(f"Error generating audio with ElevenLabs: {e}")
        return None, 0

# --- 2. Text-to-Image Generation (Using RunwayML) ---
def wait_for_image(task_id, runway):
    """
    Polls the RunwayML API to check the status of the text-to-image task.
    Once completed, it returns the URL of the generated image.
    """
    print("Waiting for image to be generated...")
    while True:
        try:
            task = runway.tasks.retrieve(task_id)
            status = task.status
            print(f"Image Task Status: {status}")

            if status == "SUCCEEDED":
                print("Image generated successfully!")
                return task.output[0]  # The first output is the image URL
            elif status == "FAILED":
                print("Image generation failed.")
                return None

            time.sleep(5)  # Wait for 5 seconds before checking again
        except Exception as e:
            print(f"Error retrieving image task status: {e}")
            return None


def generate_image_from_text(prompt, runway):
    """
    Generates an image from a text prompt using the RunwayML API.
    """
    print("Creating text-to-image task...")
    try:
        # Create a new text-to-image task
        # Reverting to the 'ratio' parameter as 'width'/'height' are not supported by the SDK
        task = runway.text_to_image.create(
            prompt_text=prompt,
            model="gen4_image", # Using a dedicated text-to-image model
            ratio='1920:1080'                   # Using ratio to specify aspect ratio
        )
        print(f"Image task created with ID: {task.id}")

        # Wait for the image to be generated and get its URL
        image_url = wait_for_image(task.id, runway)
        return image_url
    except Exception as e:
        print(f"Error creating RunwayML text-to-image task: {e}")
        return None


# --- 3. Image-to-Video Generation ---
def generate_video_from_image(image_url, prompt, duration, runway):
    """
    Generates a video from an image URL using the RunwayML API.
    """
    print(f"Creating image-to-video task with a duration of {duration} seconds...")
    try:
        # Create a new image-to-video task
        task = runway.image_to_video.create(
            prompt_image=image_url,
            prompt_text=prompt,
            model="gen4_turbo",
              ratio='720:1280',
            duration=duration, # Set video duration based on audio length
        )
        print(f"Video task created with ID: {task.id}")
        return task.id
    except Exception as e:
        print(f"Error creating RunwayML image-to-video task: {e}")
        return None

# --- 4. Task Polling and Video Retrieval ---
def wait_for_video(task_id, runway):
    """
    Polls the RunwayML API to check the status of the video generation task.
    Once completed, it downloads the video and returns its local path.
    """
    print("Waiting for video to be generated...")
    while True:
        try:
            task = runway.tasks.retrieve(task_id)
            status = task.status
            print(f"Video Task Status: {status}")

            if status == "SUCCEEDED":
                print("Video generated successfully!")
                video_url = task.output[0]
                video_path = download_video(video_url, f"runway_video_{task_id}.mp4")
                return video_path
            elif status == "FAILED":
                print("Video generation failed.")
                return None

            time.sleep(10)  # Wait for 10 seconds before checking again
        except Exception as e:
            print(f"Error retrieving video task status: {e}")
            return None

def download_video(url, filename):
    """Downloads the generated video from a URL and returns the file path."""
    print(f"Downloading video from: {url}")
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            os.makedirs("generated_videos", exist_ok=True)
            filepath = os.path.join("generated_videos", filename)
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"Video saved as {filepath}")
            return filepath
        else:
            print(f"Error downloading video: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error downloading video: {e}")
        return None

# --- 5. Combine Audio and Video ---
def combine_audio_and_video(video_path, audio_path, output_filename="final_video.mp4"):
    """
    Combines a video file with an audio file using moviepy.
    """
    if not video_path or not audio_path:
        print("Missing video or audio path for combining.")
        return

    print("Combining video and audio...")
    try:
        video_clip = VideoFileClip(video_path)
        audio_clip = AudioFileClip(audio_path)

        # FIX: Set the audio of the video clip by assigning to the .audio attribute
        video_clip.audio = audio_clip

        # Ensure the final clip duration matches the video or audio, whichever is shorter
        video_clip.duration = min(video_clip.duration, audio_clip.duration)

        # Create a directory for the final output
        os.makedirs("final_output", exist_ok=True)
        output_path = os.path.join("final_output", output_filename)

        # Write the result to a file
        video_clip.write_videofile(output_path, codec="libx264", audio_codec="aac")

        print(f"Final video with new audio saved to {output_path}")

        # Clean up by closing the clips
        video_clip.close()
        audio_clip.close()

    except Exception as e:
        print(f"Error combining video and audio: {e}")


# --- Main Execution ---
if __name__ == "__main__":
    if not RUNWAYML_API_SECRET or not ELEVENLABS_API_KEY:
        print("API key(s) not found. Please set RUNWAYML_API_SECRET and ELEVENLABS_API_KEY in your .env file.")
    else:
        # --- Your Inputs ---
        # Text for the audio narration
        narration_text = "In the heart of the digital arena, a hackathon powered by Hugging Face unfolds. Here, coders, fueled by caffeine and ambition, wrestle with complex algorithms. The air is thick with the silent hum of servers and the quiet despair of a thousand bugs. Yet, through the haze of exhaustion, brilliance sparks."
        # Text prompt for the visual part of the video
        visual_prompt = "A cinematic, realistic shot of a hackathon organized by Hugging Face. Stressed and depressed coders are staring at their screens in a dimly lit, modern office space."
        # --- End of Inputs ---

        # 1. Generate audio and get its duration
        audio_file_path, audio_duration_sec = generate_audio_from_text(narration_text)

        if audio_file_path and audio_duration_sec > 0:
            # FIX: RunwayML API requires duration to be exactly 5 or 10.
            # We will choose the closest valid value to the actual audio length.
            calculated_duration = math.ceil(audio_duration_sec)
            
            if calculated_duration > 7:  # If audio is 8 seconds or longer, use a 10-second video
                video_duration = 10
            else:  # Otherwise, default to a 5-second video
                video_duration = 5
            
            print(f"Original audio duration: {audio_duration_sec:.2f}s. Adjusted video duration to {video_duration}s to meet RunwayML API requirements.")


            try:
                # Initialize RunwayML Client
                print("Initializing RunwayML client...")
                runway_client = RunwayML(api_key=RUNWAYML_API_SECRET)
                print("RunwayML client initialized.")

                # 2. Generate an image from the text prompt
                generated_image_url = generate_image_from_text(visual_prompt, runway_client)

                if generated_image_url:
                    print(f"Generated Image URL: {generated_image_url}")
                    # 3. Generate a video from the image, with duration matching the audio
                    video_task_id = generate_video_from_image(generated_image_url, visual_prompt, video_duration, runway_client)

                    if video_task_id:
                        # 4. Wait for the video and get its local path
                        downloaded_video_path = wait_for_video(video_task_id, runway_client)

                        if downloaded_video_path:
                             # 5. Combine the downloaded video with the generated audio
                            combine_audio_and_video(downloaded_video_path, audio_file_path, f"final_video_{video_task_id}.mp4")

            except Exception as e:
                print(f"An error occurred during the main execution: {e}")



# ##############################################################################
# ##############################################################################
#
# --- SCRIPT 2: ADD AUDIO TO AN EXISTING LOCAL VIDEO ---
#
# This script takes a video file from your computer, generates audio from text,
# and combines them into a new video file.
#
# ##############################################################################
# ##############################################################################

import os
import math
from elevenlabs import *
from moviepy import *
from mutagen import *
from dotenv import load_dotenv

def generate_audio_for_local_video(text, filename="local_video_audio.mp3"):
    """
    Generates audio from text using the ElevenLabs API.
    """
    load_dotenv()
    api_key = "sk_241963330f418ebe22a57719bb28b1984a38c8839f35dc64"
    if not api_key:
        print("ElevenLabs API key not found in .env file.")
        return None
    
    print("Generating audio from text with ElevenLabs...")
    try:
        client = ElevenLabs(api_key=api_key)
        audio = client.text_to_speech.convert(
            text=text,
            voice_id="21m00Tcm4TlvDq8ikWAM",
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128"
        )
        os.makedirs("generated_audio", exist_ok=True)
        audio_path = os.path.join("generated_audio", filename)
        save(audio, audio_path)
        print(f"Audio for local video saved successfully to {audio_path}")
        return audio_path
    except Exception as e:
        print(f"Error generating audio for local video: {e}")
        return None

def combine_local_video_with_audio(video_path, audio_path, output_path="final_local_video.mp4"):
    """
    Combines a local video file with a generated audio file.
    """
    if not os.path.exists(video_path):
        print(f"Error: Input video not found at '{video_path}'")
        return
    if not os.path.exists(audio_path):
        print(f"Error: Input audio not found at '{audio_path}'")
        return

    print("Combining local video and generated audio...")
    try:
        video_clip = VideoFileClip(video_path)
        audio_clip = AudioFileClip(audio_path)

        # Set the video's audio to the newly generated audio
        video_clip.audio = audio_clip
        
        # Ensure the final clip's duration does not exceed the video's original duration
        if audio_clip.duration > video_clip.duration:
             print(f"Warning: Audio duration ({audio_clip.duration}s) is longer than video duration ({video_clip.duration}s). The final video will be truncated to the video's length.")
             video_clip.duration = video_clip.duration
        else:
             video_clip.duration = audio_clip.duration


        os.makedirs("final_output", exist_ok=True)
        final_output_path = os.path.join("final_output", output_path)
        
        video_clip.write_videofile(final_output_path, codec="libx264", audio_codec="aac")

        print(f"Final video with new audio saved to {final_output_path}")
        
        video_clip.close()
        audio_clip.close()

    except Exception as e:
        print(f"Error combining local video and audio: {e}")

if __name__ == "__main__":
    # --- This part is ONLY for the second script ---
    # --- To run it, you can comment out the main block of the first script ---

    print("\n--- Running Script 2: Add Audio to Local Video ---")
    
    # --- Your Inputs for Script 2 ---
    # 1. The path to the video file on your computer.
    #    (Use forward slashes / even on Windows)
    input_video_path = "media/finalvideo.mp4" 
    
    # 2. The text you want to convert to speech for the video.
    local_narration_text = "Manfredi is from Sicily and will harm you if you are not nice, don't play with him you porco due. Cazzo porco lorem ipsum Cazzo porco lorem ipsum Cazzo porco lorem ipsum Cazzo porco lorem ipsum"

    # 3. The name of the final output file.
    output_video_filename = "my_video_with_new_sound.mp4"
    # --- End of Inputs ---
    
    # Step 1: Generate the audio
    generated_audio_path = generate_audio_for_local_video(local_narration_text)
    
    # Step 2: If audio was created successfully, combine it with the local video
    if generated_audio_path:
        combine_local_video_with_audio(input_video_path, generated_audio_path, output_video_filename)