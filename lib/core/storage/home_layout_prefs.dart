import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

class HomeLayoutConfig {
  final List<String> orderedSections;
  final Set<String> hiddenSections;

  const HomeLayoutConfig({
    required this.orderedSections,
    required this.hiddenSections,
  });

  const HomeLayoutConfig.empty()
    : orderedSections = const [],
      hiddenSections = const {};

  HomeLayoutConfig copyWith({
    List<String>? orderedSections,
    Set<String>? hiddenSections,
  }) {
    return HomeLayoutConfig(
      orderedSections: orderedSections ?? this.orderedSections,
      hiddenSections: hiddenSections ?? this.hiddenSections,
    );
  }

  Map<String, dynamic> toJson() {
    return {'order': orderedSections, 'hidden': hiddenSections.toList()};
  }

  factory HomeLayoutConfig.fromJson(Map<String, dynamic> json) {
    final order = json['order'];
    final hidden = json['hidden'];
    return HomeLayoutConfig(
      orderedSections: order is List
          ? order.map((item) => item.toString()).toList()
          : const [],
      hiddenSections: hidden is List
          ? hidden.map((item) => item.toString()).toSet()
          : const {},
    );
  }
}

class HomeLayoutPrefs {
  static const _storageKey = 'home_layout_config_v1';

  static Future<HomeLayoutConfig> load() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString(_storageKey);
      if (raw == null || raw.isEmpty) {
        return const HomeLayoutConfig.empty();
      }
      final parsed = jsonDecode(raw);
      if (parsed is! Map<String, dynamic>) {
        return const HomeLayoutConfig.empty();
      }
      return HomeLayoutConfig.fromJson(parsed);
    } catch (_) {
      return const HomeLayoutConfig.empty();
    }
  }

  static Future<void> save(HomeLayoutConfig config) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_storageKey, jsonEncode(config.toJson()));
  }
}
