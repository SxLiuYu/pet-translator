// mobile-app/lib/main.dart
// 毛孩子翻译官 Flutter App 入口
import 'package:flutter/material.dart';
import 'screens/home_screen.dart';
import 'screens/report_screen.dart';
import 'screens/events_screen.dart';

void main() {
  runApp(const PetTranslatorApp());
}

class PetTranslatorApp extends StatelessWidget {
  const PetTranslatorApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '🐾 毛孩子翻译官',
      theme: ThemeData(
        colorSeed: Colors.amber,
        useMaterial3: true,
      ),
      home: const MainScreen(),
    );
  }
}

class MainScreen extends StatefulWidget {
  const MainScreen({super.key});

  @override
  State<MainScreen> createState() => _MainScreenState();
}

class _MainScreenState extends State<MainScreen> {
  int _currentIndex = 0;

  final _screens = const [
    HomeScreen(),
    EventsScreen(),
    ReportScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: _screens[_currentIndex],
      bottomNavigationBar: NavigationBar(
        selectedIndex: _currentIndex,
        onDestinationSelected: (i) => setState(() => _currentIndex = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.mic), label: "实时监听"),
          NavigationDestination(icon: Icon(Icons.history), label: "行为记录"),
          NavigationDestination(icon: Icon(Icons.analytics), label: "每日报告"),
        ],
      ),
    );
  }
}
