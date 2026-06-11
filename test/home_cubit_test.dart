import 'package:flutter_test/flutter_test.dart';
import 'package:omnisource/presentation/bloc/home/home_cubit.dart';

import 'test_fakes.dart';

void main() {
  group('HomeCubit', () {
    late FakeContentRepository repository;
    late HomeCubit cubit;

    setUp(() {
      repository = FakeContentRepository();
      cubit = HomeCubit(repository);
    });

    tearDown(() async {
      await cubit.close();
    });

    test(
      'loadContent uses home map overrides for trending and for-you',
      () async {
        final trendingFallback = makeContent(
          id: 't1',
          externalId: 't1',
          type: 'movie',
          title: 'Trending fallback',
          rating: 5,
        );
        final recsFallback = makeContent(
          id: 'r1',
          externalId: 'r1',
          type: 'movie',
          title: 'Recs fallback',
          rating: 6,
        );
        final trendingFromHome = makeContent(
          id: 't2',
          externalId: 't2',
          type: 'movie',
          title: 'Trending from home',
          rating: 9,
        );
        final recsFromHome = makeContent(
          id: 'r2',
          externalId: 'r2',
          type: 'movie',
          title: 'For you from home',
          rating: 8,
        );

        repository.trendingResponse = [trendingFallback];
        repository.recommendationsResponse = [recsFallback];
        repository.homeDataResponse = {
          'Trending Now': [trendingFromHome],
          'For You': [recsFromHome],
          'Extra': [
            makeContent(id: 'x', externalId: 'x', type: 'movie', title: 'X'),
          ],
        };

        await cubit.loadContent();

        expect(cubit.state.isLoading, isFalse);
        expect(cubit.state.error ?? '', isEmpty);
        expect(cubit.state.trending.first.externalId, 't2');
        expect(cubit.state.recommendations.first.externalId, 'r2');
        expect(cubit.state.homeMap.containsKey('Extra'), isTrue);
        expect(repository.trendingCalls, 0);
        expect(repository.lastRecommendationsType, 'music');
        expect(repository.lastHomeType, 'music');
      },
    );

    test('setCategory triggers loading for selected type', () async {
      repository.homeDataResponse = const {};

      cubit.setCategory(ContentCategory.book);
      await Future<void>.delayed(const Duration(milliseconds: 10));

      expect(cubit.state.category, ContentCategory.book);
      expect(repository.trendingCalls, 0);
      expect(repository.lastRecommendationsType, 'book');
      expect(repository.lastHomeType, 'book');
    });

    test('loadContent sets error on repository failure', () async {
      repository.homeDataError = Exception('boom');

      await cubit.loadContent();

      expect(cubit.state.isLoading, isFalse);
      expect(repository.homeDataCalls, 1);
      expect(cubit.state.trending, isEmpty);
    });

    test('toggleLike forwards to repository', () async {
      final item = makeContent(
        id: '1',
        externalId: 'ext-1',
        type: 'movie',
        title: 'Item',
      );

      await cubit.toggleLike(item);

      expect(repository.toggleLikeCalls, 1);
      expect(repository.lastToggledContent?.externalId, 'ext-1');
    });

    test('setCategory with same category does nothing', () async {
      repository.homeDataResponse = const {};

      cubit.setCategory(ContentCategory.music);
      await Future<void>.delayed(const Duration(milliseconds: 10));

      expect(repository.trendingCalls, 0);
      expect(cubit.state.category, ContentCategory.music);
    });

    test('uses "Trending" key when "Trending Now" is absent', () async {
      final trendingFromLegacy = makeContent(
        id: 'legacy',
        externalId: 'legacy',
        type: 'movie',
        title: 'Legacy Trending',
      );
      repository.trendingResponse = [
        makeContent(
          id: 'fallback',
          externalId: 'fallback',
          type: 'movie',
          title: 'Fallback',
        ),
      ];
      repository.recommendationsResponse = const [];
      repository.homeDataResponse = {
        'Trending': [trendingFromLegacy],
      };

      await cubit.loadContent();

      expect(cubit.state.trending.first.externalId, 'legacy');
    });

    test(
      'falls back to recommendations response when "For You" is absent',
      () async {
        final fallbackRec = makeContent(
          id: 'rec-fallback',
          externalId: 'rec-fallback',
          type: 'movie',
          title: 'Fallback rec',
        );
        repository.trendingResponse = const [];
        repository.recommendationsResponse = [fallbackRec];
        repository.homeDataResponse = {'Trending Now': const []};

        await cubit.loadContent();

        expect(cubit.state.recommendations.length, 1);
        expect(cubit.state.recommendations.first.externalId, 'rec-fallback');
      },
    );

    test('loadContent stores readable error text when request fails', () async {
      repository.homeDataError = Exception('home broken');

      await cubit.loadContent();

      expect(cubit.state.isLoading, isFalse);
      expect(cubit.state.error, contains('Ошибка загрузки'));
    });
  });
}
