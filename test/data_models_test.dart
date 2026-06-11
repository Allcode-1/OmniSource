import 'package:flutter_test/flutter_test.dart';
import 'package:omnisource/core/constants/api_constants.dart';
import 'package:omnisource/data/models/app_notification_model.dart';
import 'package:omnisource/data/models/content_model.dart';
import 'package:omnisource/data/models/interaction_event_model.dart';
import 'package:omnisource/data/models/playlist_model.dart';
import 'package:omnisource/data/models/usage_stats_model.dart';
import 'package:omnisource/data/models/user_model.dart';
import 'package:omnisource/domain/entities/unified_content.dart';

void main() {
  group('ContentModel', () {
    test('fromJson maps aliases and normalizes image url', () {
      final model = ContentModel.fromJson({
        '_id': '1',
        'ext_id': 'ext-1',
        'type': 'movie',
        'title': 'Blade Runner',
        'subtitle': 'Movie',
        'description': 'Desc',
        'image_url': 'https://image.tmdb.org/t/p/w500/a.jpg',
        'rating': 8.5,
        'genres': ['Sci-Fi'],
        'release_date': '1982-06-25',
      });

      expect(model.id, '1');
      expect(model.externalId, 'ext-1');
      expect(model.type, 'movie');
      expect(model.title, 'Blade Runner');
      expect(model.imageUrl, startsWith(ApiConstants.baseUrl));
      expect(model.rating, 8.5);
      expect(model.genres, ['Sci-Fi']);
    });

    test('fromJson falls back to empty model on invalid payload', () {
      final model = ContentModel.fromJson(null);
      expect(model.type, 'unknown');
      expect(model.title, 'Loading Error');
    });

    test('fromEntity + toJson keeps key values', () {
      final entity = UnifiedContent(
        id: 'id-x',
        externalId: 'ext-x',
        type: 'music',
        title: 'Track',
        subtitle: 'Artist',
        imageUrl: 'https://img',
        rating: 7.2,
        genres: const ['Pop'],
      );
      final model = ContentModel.fromEntity(entity);
      final json = model.toJson();

      expect(json['_id'], 'id-x');
      expect(json['ext_id'], 'ext-x');
      expect(json['type'], 'music');
      expect(json['genres'], ['Pop']);
    });
  });

  group('Other data models', () {
    test('UserModel parses identifiers and fields', () {
      final model = UserModel.fromJson({
        '_id': 'u1',
        'email': 'user@test.dev',
        'username': 'neo',
        'is_onboarding_completed': true,
        'interests': ['action', 'noir'],
      });

      expect(model.id, 'u1');
      expect(model.isOnboardingCompleted, isTrue);
      expect(model.interests, ['action', 'noir']);
    });

    test('PlaylistModel parses id and items', () {
      final model = PlaylistModel.fromJson({
        '_id': 'p1',
        'title': 'Favorites',
        'description': 'desc',
        'items': ['a', 'b'],
      });

      expect(model.id, 'p1');
      expect(model.title, 'Favorites');
      expect(model.items.length, 2);
    });

    test('InteractionEventModel defaults on malformed date', () {
      final before = DateTime.now();
      final model = InteractionEventModel.fromJson({
        'id': 'i1',
        'type': 'view',
        'ext_id': 'ext-1',
        'created_at': 'not-a-date',
      });

      expect(model.id, 'i1');
      expect(model.type, 'view');
      expect(model.extId, 'ext-1');
      expect(
        model.createdAt.isAfter(before.subtract(const Duration(seconds: 2))),
        isTrue,
      );
    });

    test('UsageStatsModel parses nested metrics map', () {
      final model = UsageStatsModel.fromJson({
        'total_events': 12,
        'counts_by_type': {'view': 10, 'like': 2},
        'ctr': 0.3,
        'save_rate': 0.2,
        'avg_dwell_seconds': 11.4,
        'top_content_types': {'movie': 8},
        'ab_metrics': {
          'hybrid_ml': {'ctr': 0.4, 'save_rate': 0.1},
        },
      });

      expect(model.totalEvents, 12);
      expect(model.countsByType['view'], 10);
      expect(model.abMetrics['hybrid_ml']?['ctr'], 0.4);
    });

    test('AppNotificationModel has fallback level and parse date', () {
      final model = AppNotificationModel.fromJson({
        'id': 'n1',
        'title': 'Title',
        'body': 'Body',
        'created_at': '2025-01-01T00:00:00Z',
      });

      expect(model.id, 'n1');
      expect(model.level, 'info');
      expect(model.createdAt.year, 2025);
    });
  });
}
