import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:omnisource/core/storage/home_layout_prefs.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  group('HomeLayoutConfig', () {
    test('copyWith preserves values', () {
      const config = HomeLayoutConfig(
        orderedSections: ['Trending Now'],
        hiddenSections: {'For You'},
      );

      final updated = config.copyWith(
        orderedSections: ['For You', 'Trending Now'],
      );

      expect(updated.orderedSections, ['For You', 'Trending Now']);
      expect(updated.hiddenSections, {'For You'});
    });

    test('toJson and fromJson roundtrip', () {
      const config = HomeLayoutConfig(
        orderedSections: ['A', 'B'],
        hiddenSections: {'C'},
      );
      final parsed = HomeLayoutConfig.fromJson(config.toJson());
      expect(parsed.orderedSections, ['A', 'B']);
      expect(parsed.hiddenSections, {'C'});
    });
  });

  group('HomeLayoutPrefs', () {
    test('load returns empty config when storage is empty', () async {
      SharedPreferences.setMockInitialValues({});

      final config = await HomeLayoutPrefs.load();
      expect(config.orderedSections, isEmpty);
      expect(config.hiddenSections, isEmpty);
    });

    test('save and load persisted config', () async {
      SharedPreferences.setMockInitialValues({});
      const config = HomeLayoutConfig(
        orderedSections: ['Trending Now', 'For You'],
        hiddenSections: {'Legacy'},
      );

      await HomeLayoutPrefs.save(config);
      final loaded = await HomeLayoutPrefs.load();

      expect(loaded.orderedSections, ['Trending Now', 'For You']);
      expect(loaded.hiddenSections, {'Legacy'});
    });

    test('load gracefully handles invalid JSON', () async {
      SharedPreferences.setMockInitialValues({
        'home_layout_config_v1': '{invalid-json',
      });

      final loaded = await HomeLayoutPrefs.load();
      expect(loaded.orderedSections, isEmpty);
      expect(loaded.hiddenSections, isEmpty);
    });

    test('load handles non-map JSON by returning empty', () async {
      SharedPreferences.setMockInitialValues({
        'home_layout_config_v1': jsonEncode(['not-a-map']),
      });

      final loaded = await HomeLayoutPrefs.load();
      expect(loaded.orderedSections, isEmpty);
      expect(loaded.hiddenSections, isEmpty);
    });
  });
}
