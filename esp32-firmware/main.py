"""
毛孩子翻译官 - ESP32-S3 音频采集端 (MicroPython)
硬件: ESP32-S3 + INMP441 I2S 麦克风
功能: VAD 检测到声音 → 录制3s → WiFi上传到服务器
"""
import machine
import network
import urequests
import ustruct
import time
import json

# ========== 配置 ==========
WIFI_SSID = "你的WiFi"
WIFI_PASS = "密码"
SERVER_URL = "http://192.168.1.100:8000/api/upload_audio"
I2S_SCK = 4
I2S_WS  = 5
I2S_SD  = 6
SAMPLE_RATE = 16000
SAMPLE_BITS = 16
RECORD_SECONDS = 3
BUFFER_SIZE = 1024

# ========== WiFi ==========
def connect_wifi():
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    sta.connect(WIFI_SSID, WIFI_PASS)
    for _ in range(20):
        if sta.isconnected():
            print("WiFi OK:", sta.ifconfig())
            return sta
        time.sleep_ms(500)
    raise RuntimeError("WiFi连接失败")

# ========== I2S 麦克风初始化 ==========
def init_i2s():
    i2s = machine.I2S(
        0,
        sck=machine.Pin(I2S_SCK),
        ws=machine.Pin(I2S_WS),
        sd=machine.Pin(I2S_SD),
        mode=machine.I2S.RX,
        bits=SAMPLE_BITS,
        format=machine.I2S.MONO,
        rate=SAMPLE_RATE,
        ibuf=BUFFER_SIZE * 2,
    )
    return i2s

# ========== VAD (简单能量阈值) ==========
def is_speech(data, threshold=500):
    """简单能量检测，检测到声音返回 True"""
    samples = ustruct.unpack(f"<{len(data)//2}h", data)
    energy = sum(abs(s) for s in samples) / len(samples)
    return energy > threshold

# ========== 录音 ==========
def record_chunk(i2s, seconds=3):
    total_samples = SAMPLE_RATE * seconds
    raw = bytearray(total_samples * 2)
    read = 0
    while read < len(raw):
        n = i2s.readinto(raw[read:read+BUFFER_SIZE])
        if n:
            read += n
        else:
            time.sleep_ms(10)
    return bytes(raw)

# ========== 主循环 ==========
def main():
    connect_wifi()
    i2s = init_i2s()
    print("🎤 毛孩子翻译官启动，监听中...")

    buf = bytearray(BUFFER_SIZE)
    while True:
        n = i2s.readinto(buf)
        if n and is_speech(bytes(buf[:n])):
            print("🔊 检测到声音，开始录音", RECORD_SECONDS, "秒...")
            audio_data = record_chunk(i2s, RECORD_SECONDS)
            print("录音完成，上传中...")

            try:
                boundary = "----FormBoundary7MA4YWxkTrZu0gW"
                body = (
                    "--" + boundary + "\r\n"
                    'Content-Disposition: form-data; name="file"; filename="pet.wav"\r\n'
                    "Content-Type: audio/wav\r\n\r\n"
                ).encode() + audio_data + (
                    "\r\n--" + boundary + "--\r\n"
                ).encode()

                resp = urequests.post(
                    SERVER_URL,
                    data=body,
                    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                )
                result = resp.json()
                print("✅ 识别结果:", result)
                resp.close()
            except Exception as e:
                print("❌ 上传失败:", e)

            time.sleep_ms(2000)

if __name__ == "__main__":
    main()
