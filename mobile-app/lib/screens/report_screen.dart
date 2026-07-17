// screens/report_screen.dart
// 每日报告页 - 健康评分 + 行为分布图 + 陪玩建议
import 'package:flutter/material.dart';

class ReportScreen extends StatelessWidget {
  const ReportScreen({super.key});

  final Map<String, dynamic> _sampleReport = const {
    "date": "2026-07-16",
    "health_score": 75,
    "health_status": "🙂 状态正常",
    "total_events": 15,
    "alert_count": 2,
    "animals_detected": ["狗", "猫"],
    "event_breakdown": {
      "狗-吠叫": 8,
      "猫-喵叫": 5,
      "猫-呼噜": 2,
    },
    "suggestions": [
      "🐕 狗狗白天吠叫偏多，建议增加遛狗时长",
      "🐱 猫咪夜间活跃，睡前陪玩消耗精力",
    ],
    "hourly_chart": {
      "9": {"total": 3, "alerts": 1},
      "14": {"total": 5, "alerts": 0},
      "22": {"total": 4, "alerts": 1},
    },
  };

  @override
  Widget build(BuildContext context) {
    final report = _sampleReport;
    final score = report["health_score"] as int;
    final scoreColor = score >= 80
        ? Colors.green : score >= 60 ? Colors.orange : Colors.red;

    return Scaffold(
      appBar: AppBar(
        title: const Text("📊 每日报告"),
        backgroundColor: Theme.of(context).colorScheme.inversePrimary,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text("📅 ${report["date"]}",
                 style: const TextStyle(fontSize: 14, color: Colors.grey)),
            const SizedBox(height: 16),
            _ScoreCard(score: score, color: scoreColor, status: report["health_status"]),
            const SizedBox(height: 16),
            Row(
              children: [
                _StatCard(icon: Icons.bar_chart, label: "总事件", value: "${report["total_events"]}"),
                const SizedBox(width: 12),
                _StatCard(icon: Icons.warning_amber, label: "警报", value: "${report["alert_count"]}", color: Colors.orange),
              ],
            ),
            const SizedBox(height: 16),
            const _SectionTitle("📈 行为分布"),
            const SizedBox(height: 8),
            ...(_sampleReport["event_breakdown"] as Map).entries.map((e) {
              return _BehaviorBar(label: e.key, count: e.value as int);
            }).toList(),
            const SizedBox(height: 24),
            const _SectionTitle("💡 今日陪玩建议"),
            const SizedBox(height: 8),
            ...(report["suggestions"] as List).map((s) => Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text("• ", style: TextStyle(fontSize: 18)),
                  Expanded(child: Text(s, style: const TextStyle(fontSize: 14))),
                ],
              ),
            )).toList(),
            const SizedBox(height: 32),
            Center(
              child: ElevatedButton.icon(
                onPressed: () {},
                icon: const Icon(Icons.send),
                label: const Text("发送报告到微信"),
                style: ElevatedButton(
                  backgroundColor: Colors.green,
                  foregroundColor: Colors.white,
                ),
              ),
            ),
            const SizedBox(height: 32),
          ],
        ),
      ),
    );
  }
}

class _ScoreCard extends StatelessWidget {
  final int score;
  final Color color;
  final String status;

  const _ScoreCard({required this.score, required this.color, required this.status});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(colors: [color.withOpacity(0.8), color]),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          Stack(
            alignment: Alignment.center,
            children: [
              SizedBox(width: 70, height: 70,
                child: CircularProgressIndicator(
                  value: score / 100,
                  strokeWidth: 6,
                  backgroundColor: Colors.white30,
                  valueColor: const AlwaysStoppedAnimation(Colors.white),
                ),
              ),
              Text("$score",
                  style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: Colors.white)),
            ],
          ),
          const SizedBox(width: 20),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(status, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.white)),
                const SizedBox(height: 4),
                const Text("综合精神状态评分", style: TextStyle(fontSize: 12, color: Colors.white70)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _StatCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final Color? color;

  const _StatCard({required this.icon, required this.label, required this.value, this.color});

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: (color ?? Theme.of(context).colorScheme.primaryContainer).withOpacity(0.6),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          children: [
            Icon(icon, color: color ?? Theme.of(context).colorScheme.primary),
            const SizedBox(width: 12),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(value, style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: color)),
                Text(label, style: const TextStyle(fontSize: 12, color: Colors.grey)),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  final String title;
  const _SectionTitle(this.title);

  @override
  Widget build(BuildContext context) {
    return Text(title, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold));
  }
}

class _BehaviorBar extends StatelessWidget {
  final String label;
  final int count;

  const _BehaviorBar({required this.label, required this.count});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          SizedBox(width: 100, child: Text(label, style: const TextStyle(fontSize: 13))),
          Expanded(
            child: LayoutBuilder(
              builder: (ctx, constraints) {
                final maxCount = 10;
                final width = max(1, (count / maxCount)) * constraints.maxWidth;
                return Stack(
                  children: [
                    Container(height: 20, width: constraints.maxWidth,
                      color: Colors.grey.shade200, borderRadius: BorderRadius.circular(4)),
                    AnimatedContainer(
                      height: 20, width: width,
                      duration: const Duration(milliseconds: 500),
                      decoration: BoxDecoration(
                        color: Colors.amber, borderRadius: BorderRadius.circular(4),
                      ),
                    ),
                    if (count > 0)
                      Positioned(left: 8, top: 2,
                        child: Text("$count 次", style: const TextStyle(fontSize: 11, color: Colors.black54))),
                  ],
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
