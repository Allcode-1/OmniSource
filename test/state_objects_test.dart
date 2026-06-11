import 'package:flutter_test/flutter_test.dart';
import 'package:omnisource/data/models/playlist_model.dart';
import 'package:omnisource/domain/entities/user.dart';
import 'package:omnisource/presentation/bloc/auth/auth_state.dart';
import 'package:omnisource/presentation/bloc/home/home_cubit.dart';
import 'package:omnisource/presentation/bloc/library/library_state.dart';
import 'package:omnisource/presentation/bloc/search/search_state.dart';

import 'test_fakes.dart';

void main() {
  group('State objects', () {
    test('HomeState copyWith updates selected fields', () {
      final base = HomeState(
        category: ContentCategory.movie,
        trending: [
          makeContent(
            id: 't1',
            externalId: 't1',
            type: 'movie',
            title: 'Trending 1',
          ),
        ],
        isLoading: true,
        error: 'old',
      );

      final updated = base.copyWith(
        category: ContentCategory.book,
        isLoading: false,
        error: '',
      );

      expect(updated.category, ContentCategory.book);
      expect(updated.isLoading, isFalse);
      expect(updated.error, '');
      expect(updated.trending.length, 1);
    });

    test('LibraryLoaded copyWith preserves fields when omitted', () {
      final initial = LibraryLoaded(
        favorites: [
          makeContent(id: 'f1', externalId: 'f1', type: 'movie', title: 'Fav'),
        ],
        playlists: [PlaylistModel(id: 'p1', title: 'P1', items: const [])],
        playlistItemsById: {
          'p1': [
            makeContent(
              id: 'i1',
              externalId: 'i1',
              type: 'music',
              title: 'Track',
            ),
          ],
        },
      );

      final updated = initial.copyWith(
        favorites: [
          makeContent(id: 'f2', externalId: 'f2', type: 'book', title: 'Fav 2'),
        ],
      );

      expect(updated.favorites.single.externalId, 'f2');
      expect(updated.playlists.single.id, 'p1');
      expect(updated.playlistItemsById['p1']?.single.externalId, 'i1');
    });

    test('SearchState copyWith clears year bounds when flags are set', () {
      final base = SearchState(
        fromYear: 2000,
        toYear: 2020,
        minRating: 7.5,
        onlyLiked: true,
      );

      final updated = base.copyWith(
        clearFromYear: true,
        clearToYear: true,
        minRating: 8.0,
      );

      expect(updated.fromYear, isNull);
      expect(updated.toYear, isNull);
      expect(updated.minRating, 8.0);
      expect(updated.onlyLiked, isTrue);
    });

    test('Auth states hold payload values', () {
      final user = User(
        id: 'u1',
        email: 'neo@test.dev',
        username: 'neo',
        isOnboardingCompleted: false,
      );
      final authenticated = AuthAuthenticated(
        user: user,
        needsOnboarding: true,
      );
      final error = AuthError('boom');

      expect(authenticated.user.id, 'u1');
      expect(authenticated.needsOnboarding, isTrue);
      expect(error.message, 'boom');
      expect(AuthInitial(), isA<AuthState>());
      expect(AuthLoading(), isA<AuthState>());
    });
  });
}
