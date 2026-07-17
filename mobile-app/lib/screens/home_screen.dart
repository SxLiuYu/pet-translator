// screens/home_screen.dart
// 实时监听页 - 声纹 + 摄像头画面 + 实时行为事件
import 'package:flutter/material.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  WebSocketChannel? _audioChannel;
  WebSocketChannel? _cameraChannel;
  List<Map<String, dynamic>> _events = [];
  bool _isListening = false;
  bool _isCameraOn = false;
  String? _latestAnnotatedJpeg;  // base64 编码的标注图

  final String _serverIp = "192.168.1.100";

  void _toggleAudio() {
    setState(() => _isListening = !_isListening);
    if (_isListening) {
      _audioChannel = WebSocketChannel.connect(Uri.parse("ws://$_serverIp:8000/ws"));
      _audioChannel!.stream.listen((data) {
        final msg = Map<String, dynamic>.from(data);
        if (mounted) {
          setState(() {
            _events.insert(0, msg["data"] ?? msg);
            if (_events.length > 50) _events.removeLast();
          });
        }
      }, onError: (_) => setState(() => _isListening = false));
    } else {
      _audioChannel?.sink.close();
      _audioChannel = null;
    }
  }

  void _toggleCamera() async {
    setState(() => _isCameraOn = !_isCameraOn);
    if (_isCameraOn) {
      try {
        _cameraChannel = WebSocketChannel.connect(Uri.parse("ws://$_serverIp:8000/ws/camera"));
        _cameraChannel!.sink.add("cam:default");
        _cameraChannel!.stream.listen((data) async {
          if (data is List<int> && data.isNotEmpty) {
            // 解析 frame\x00<jpeg_bytes> 格式
            final bytes = Uint8List.fromList(data);
            int nullIdx = bytes.indexOf(0);
            if (nullIdx > 0) {
              final jpeg = bytes.sublist(nullIdx + 1);
              if (mounted) setState(() => _latestAnnotatedJpeg = null); // 直接传 bytes
            }
          }
        }, onError: (_) => setState(() => _isCameraOn = false));
      } catch (e) {
        setState(() => _isCameraOn = false);
      }
    } else {
      _cameraChannel?.sink.close();
      _cameraChannel = null;
      setState(() => _latestAnnotatedJpeg = null);
    }
  }

  @override
  void dispose() {
    _audioChannel?.sink.close();
    _cameraChannel?.sink.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text("🐾 实时监听"),
        backgroundColor: Theme.of(context).colorScheme.inversePrimary,
      ),
      body: Column(
        children: [
          // 摄像头画面
          _buildCameraPreview(),
          const Divider(height: 1),

          // 控制按钮
          _buildControlBar(),
          const Divider(height: 1),

          // 行为事件列表
          Expanded(
            child: _events.isEmpty
                ? const Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.pets, size: 48, color: Colors.grey),
                        SizedBox(height: 12),
                        Text("等待毛孩子发出声音...", style: TextStyle(color: Colors.grey)),
                      ],
                    ),
                  )
                : ListView.builder(
                    itemCount: _events.length,
                    itemBuilder: (ctx, i) => _buildEventCard(_events[i]),
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildCameraPreview() {
    return Container(
      height: 200,
      width: double.infinity,
      color: Colors.black,
      child: _isCameraOn
          ? StreamBuilder(
              stream: _cameraChannel?.stream,
              builder: (ctx, snapshot) {
                if (snapshot.hasData && snapshot.data is List<int>) {
                  final bytes = Uint8List.fromList(snapshot.data!);
                  int nullIdx = bytes.indexOf(0);
                  if (nullIdx > 0) {
                    final jpeg = bytes.sublist(nullIdx + 1);
                    return Image.memory(jpeg, fit: BoxFit.cover, width: double.infinity);
                  }
                }
                return const Center(
                  child: CircularProgressIndicator(color: Colors.white54),
                );
              },
            )
          : Column(
              children: [
                const Icon(Icons.videocam_off, size: 40, color: Colors.white38),
                const SizedBox(height: 8),
                Text("摄像头未开启",
                     style: TextStyle(color: Colors.grey.shade600, fontSize: 13)),
                TextButton.icon(
                  onPressed: _toggleCamera,
                  icon: const Icon(Icons.play_arrow, size: 16),
                  label: const Text("开启摄像头"),
                ),
              ],
            ),
    );
  }

  Widget _buildControlBar() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: [
          // 音频监听按钮
          Expanded(
            child: FilledButton.icon(
              onPressed: _toggleAudio,
              style: FilledButton.styleFrom(
                backgroundColor: _isListening ? Colors.red : Colors.green,
              ),
              icon: Icon(_isListening ? Icons.mic_off : Icons.mic),
              label: Text(_isListening ? "停止监听" : "开始监听"),
            ),
          ),
          const SizedBox(width: 12),
          // 摄像头按钮
          IconButton.filled(
            onPressed: _toggleCamera,
            style: IconButton.styleFrom(
              backgroundColor: _isCameraOn ? Colors.red : Colors.blue,
            ),
            icon: Icon(_isCameraOn ? Icons.videocam : Icons.videocam_off),
            tooltip: _isCameraOn ? "关闭摄像头" : "开启摄像头",
          ),
        ],
      ),
    );
  }

  Widget _buildEventCard(Map<String, dynamic> event) {
    final isAlert = event["is_alert"] == true;
    final animal = event["animal"] ?? "?";
    final behavior = event["behavior"] ?? "未知";
    final time = (event["timestamp"] ?? "").toString().substring(11, 19);
    final severity = event["severity"] ?? "info";

    final bgColor = isAlert
        ? Colors.red.shade50
        : severity == "warning"
            ? Colors.orange.shade50
            : null;

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 3),
      color: bgColor,
      child: ListTile(
        dense: true,
        leading: CircleAvatar(
          radius: 16,
          backgroundColor: isAlert ? Colors.red : Colors.amber,
          child: Text(
            animal == "狗" ? "🐕" : (animal == "猫" ? "🐱" : "❓"),
            style: const TextStyle(fontSize: 16),
          ),
        ),
        title: Text(
          "$animal · $behavior",
          style: TextStyle(fontWeight: isAlert ? FontWeight.bold : FontWeight.normal, fontSize: 14),
        ),
        subtitle: Text(event["interpretation"] ?? "", maxLines: 1, overflow: TextOverflow.ellipsis),
        trailing: Column(
          children: [
            Text(time, style: const TextStyle(fontSize: 10, color: Colors.grey)),
            if (isAlert)
              Container(
                margin: const EdgeInsets.only(top: 3),
                padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                decoration: BoxDecoration(
                  color: Colors.red, borderRadius: BorderRadius.circular(8),
                ),
                child: const Text("警报", style: TextStyle(color: Colors.white, fontSize: 9)),
              ),
          ],
        ),
      ),
    );
  }
}
