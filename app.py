from flask import Flask, request, jsonify, render_template, redirect, Response, url_for
import yt_dlp
from urllib.parse import urlparse
import requests
import threading
import time
import uuid

app = Flask(__name__)

ALLOWED_DOMAINS = {
    "yt": ["youtube.com", "www.youtube.com", "youtu.be"],
    "ig": ["instagram.com", "www.instagram.com"],
    "fb": ["facebook.com", "www.facebook.com"]
}

temp_urls = {}

def cleanup_temp_urls():
    while True:
        current_time = time.time()
        expired_keys = [key for key, data in temp_urls.items() if data['expiry'] < current_time]
        for key in expired_keys:
            del temp_urls[key]
        time.sleep(60)

threading.Thread(target=cleanup_temp_urls, daemon=True).start()

def is_valid_url(url, platform):
    parsed_url = urlparse(url)
    domain = parsed_url.netloc.lower()
    return domain in ALLOWED_DOMAINS.get(platform, [])

def get_video_info(video_url):
    ydl_opts = {'format': 'best[ext=mp4]', 'quiet': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            return {
                "video_url": info.get('url', None),
                "video_title": info.get('title', 'video'),
                "video_thumbnail": info.get('thumbnail', None),
                "caption": info.get('description', '')
            }
    except Exception:
        return None

def stream_video(video_url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(video_url, headers=headers, stream=True)
    
    if response.status_code == 200:
        def generate():
            for chunk in response.iter_content(chunk_size=1024 * 64):
                yield chunk
        
        return Response(generate(), 
                        content_type="video/mp4",
                        headers={"Content-Disposition": f"attachment; filename=video.mp4"})
    return None

def stream_image(image_url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(image_url, headers=headers, stream=True)
    
    if response.status_code == 200:
        def generate():
            for chunk in response.iter_content(chunk_size=1024 * 64):
                yield chunk
        
        return Response(generate(), 
                        content_type="image/jpeg",
                        headers={"Content-Disposition": "inline; filename=thumbnail.jpg"})
    return None

@app.route('/')
def home():
    return render_template('xtractify.html')

@app.route('/download', methods=['GET'])
def download():
        
    for platform in ["yt", "ig", "fb"]:
        video_url = request.args.get(platform)
        action = request.args.get("action")

        if video_url and is_valid_url(video_url, platform):
            video_info = get_video_info(video_url)
            if video_info and video_info["video_url"]:
                temp_id = str(uuid.uuid4())
                temp_thumbnail_id = str(uuid.uuid4())  # Thumbnail ke liye alag ID
                
                temp_urls[temp_id] = {
                    "video_url": video_info["video_url"],
                    "expiry": time.time() + 600
                }
                
                temp_urls[temp_thumbnail_id] = {
                    "image_url": video_info["video_thumbnail"],
                    "expiry": time.time() + 600
                }

                temp_download_url = url_for("temp_download", temp_id=temp_id, _external=True)
                temp_thumbnail_url = url_for("temp_thumbnail", temp_id=temp_thumbnail_id, _external=True)

                response_data = {
                    "status": "success",
                    "video_thumbnail": temp_thumbnail_url,
                    "video_title": video_info.get("video_title"),
                    "caption": video_info.get("caption"),
                    "video_url": temp_download_url
                }

                if platform == "yt" and action == "viewinfo":
                    return jsonify(response_data)

                return jsonify(response_data)

            return jsonify({"status": "error", "message": "Invalid Video Link"}), 400

    return jsonify({"status": "error", "message": "No valid parameters provided"}), 400

@app.route('/temp_download/<temp_id>')
def temp_download(temp_id):
    if temp_id in temp_urls:
        video_url = temp_urls[temp_id].get("video_url")
        if video_url:
            return stream_video(video_url) or redirect(video_url)
    return jsonify({"status": "error", "message": "Expired or Invalid URL"}), 404

@app.route('/temp_thumbnail/<temp_id>')
def temp_thumbnail(temp_id):
    if temp_id in temp_urls:
        image_url = temp_urls[temp_id].get("image_url")
        if image_url:
            return stream_image(image_url) or redirect(image_url)
    return jsonify({"status": "error", "message": "Expired or Invalid URL"}), 404

@app.route('/failed')
def failed():
    return render_template('xtractify.html')

if __name__ == '__main__':
    app.run(debug=True)
