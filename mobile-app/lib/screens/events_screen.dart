// screens/events_screen.dart
// 行为记录页 - 历史事件时间线
import 'package:flutter/material.dart';

class EventsScreen extends StatelessWidget {
  const EventsScreen({super.key});

  final List<Map<String, dynamic>> _sampleEvents = const [
    {
      "timestamp": "2026-07-16T08:23:00",
      "animal": "狗",
      "behavior": "吠叫",
      "confidence": 0.92,
      "is_alert": true,
      "interpretation": "高频短促吠叫，可能有紧急需求",
      "suggestion": "查看摄像头确认情况",
    },
    {
      "timestamp": "2026-07-16T14:05:00",
      "animal": "猫",
      "behavior": "喵叫",
      "confidence": 0.87,
      "is_alert": false,
      "interpretation": "饿了/想玩/猫砂盆需要清理",
      "suggestion": "检查食碗、猫砂盆",
    },
    {
      "timestamp": "2026-07-16T23:45:00",
      "animal": "猫",
      "behavior": "喵叫",
      "confidence": 0.91,
      "is_alert": false,
      "interpretation": "半夜喵叫，精力过剩",
      "suggestion": "睡前陪玩消耗精力",
    },
    {
      "timestamp": "2026-07-16T03:12:00",
      "animal": "狗",
      "behavior": "呜咽",
      "confidence": 0.78,
      "is_alert": true,
      "interpretation": "呜咽 = 身体不适或寻求关注",
      "suggestion": "检查身体是否有异常，陪伴安抚",
    },
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text("📋 行为记录"),
        backgroundColor: Theme.of(context).colorScheme.inversePrimary,
      ),
      body: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _sampleEvents.length,
        itemBuilder: (ctx, i) {
          final e = _sampleEvents[i];
          final time = e["timestamp"].toString().substring(11, 16);
          final animal = e["animal"];
          final behavior = e["behavior"];
          final isAlert = e["is_alert"] == true;

          return Card(
            margin: const EdgeInsets.only(bottom: 12),
            color: isAlert ? Colors.red.shade50 : null,
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text(animal == "狗" ? "🐕" : "🐱", style: const TextStyle(fontSize: 24)),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text("$animal · $behavior",
                          style: TextStyle(fontWeight: isAlert ? FontWeight.bold : FontWeight.normal, fontSize: 16),
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: (e["confidence"] > 0.8) ? Colors.green.shade100 : Colors.orange.shade100,
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Text("${(e["confidence"] * 100).toInt()}%",
                                     style: TextStyle(fontSize: 12, color: Colors.grey.shade700)),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text("📋 ${e["interpretation"]}", style: const TextStyle(fontSize: 14)),
                  const SizedBox(height: 4),
                  Text("💡 ${e["suggestion"]}", style: TextStyle(fontSize: 13, color: Colors.grey.shade600)),
                  const SizedBox(height: 8),
                  Text(time, style: TextStyle(fontSize: 11, color: Colors.grey.shade400)),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}
