import 'dart:async';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../../core/utils/app_logger.dart';
import '../../../domain/repositories/analytics_repository.dart';
import '../../../domain/repositories/content_repository.dart';
import 'search_state.dart';

class SearchCubit extends Cubit<SearchState> {
  final ContentRepository contentRepository;
  final AnalyticsRepository analyticsRepository;
  Timer? _debounce;
  int _searchToken = 0;
  static const _recentKey = 'search_recent_queries';
  static const _savedKey = 'search_saved_queries';

  SearchCubit(this.contentRepository, this.analyticsRepository)
    : super(SearchState());

  Future<void> init() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      emit(
        state.copyWith(
          recentQueries: prefs.getStringList(_recentKey) ?? const [],
          savedQueries: prefs.getStringList(_savedKey) ?? const [],
        ),
      );
    } catch (e, st) {
      AppLogger.error(
        'Search cubit init failed',
        error: e,
        stackTrace: st,
        name: 'SearchCubit',
      );
    }
  }

  Future<void> search(String query) async {
    if (_debounce?.isActive ?? false) _debounce?.cancel();

    if (query.trim().length < 2) {
      emit(
        state.copyWith(
          results: [],
          isLoading: false,
          errorMessage: '',
          lastQuery: query.trim(),
        ),
      );
      return;
    }

    _debounce = Timer(const Duration(milliseconds: 500), () {
      if (isClosed) return;
      _performSearch(query);
    });
  }

  void setFilter(String type, String currentQuery) {
    if (state.activeType == type) return;

    emit(state.copyWith(activeType: type));

    if (currentQuery.trim().length >= 2) {
      _debounce?.cancel();
      _performSearch(currentQuery);
    }
  }

  Future<void> _performSearch(String query) async {
    final token = ++_searchToken;
    final normalizedQuery = query.trim();
    final activeType = state.activeType;
    emit(state.copyWith(isLoading: true, errorMessage: ''));

    try {
      final results = await contentRepository.search(
        normalizedQuery,
        type: activeType,
      );
      if (isClosed || token != _searchToken) return;

      await _persistRecentQuery(normalizedQuery);
      await analyticsRepository.trackEvent(
        type: 'search',
        meta: {'query': normalizedQuery, 'type': activeType},
      );
      if (isClosed || token != _searchToken) return;

      emit(
        state.copyWith(
          results: results,
          isLoading: false,
          lastQuery: normalizedQuery,
        ),
      );
    } catch (e, st) {
      if (isClosed || token != _searchToken) return;
      AppLogger.error(
        'Search failed for query: $normalizedQuery',
        error: e,
        stackTrace: st,
        name: 'SearchCubit',
      );
      emit(
        state.copyWith(isLoading: false, errorMessage: 'Something went wrong'),
      );
    } finally {
      if (!isClosed && token == _searchToken && state.isLoading) {
        emit(state.copyWith(isLoading: false));
      }
    }
  }

  void clearSearch() {
    _debounce?.cancel();
    emit(
      SearchState(
        activeType: state.activeType,
        recentQueries: state.recentQueries,
        savedQueries: state.savedQueries,
        minRating: state.minRating,
        fromYear: state.fromYear,
        toYear: state.toYear,
        onlyLiked: state.onlyLiked,
      ),
    );
  }

  Future<void> saveCurrentQuery(String query) async {
    final normalized = query.trim();
    if (normalized.length < 2) return;

    final updated = [
      normalized,
      ...state.savedQueries.where((item) => item != normalized),
    ].take(30).toList();

    emit(state.copyWith(savedQueries: updated));
    final prefs = await SharedPreferences.getInstance();
    await prefs.setStringList(_savedKey, updated);
  }

  Future<void> removeSavedQuery(String query) async {
    final updated = state.savedQueries.where((item) => item != query).toList();
    emit(state.copyWith(savedQueries: updated));
    final prefs = await SharedPreferences.getInstance();
    await prefs.setStringList(_savedKey, updated);
  }

  Future<void> removeRecentQuery(String query) async {
    final updated = state.recentQueries.where((item) => item != query).toList();
    emit(state.copyWith(recentQueries: updated));
    final prefs = await SharedPreferences.getInstance();
    await prefs.setStringList(_recentKey, updated);
  }

  Future<void> clearRecentQueries() async {
    emit(state.copyWith(recentQueries: const []));
    final prefs = await SharedPreferences.getInstance();
    await prefs.setStringList(_recentKey, const []);
  }

  void setAdvancedFilters({
    double? minRating,
    int? fromYear,
    int? toYear,
    bool? onlyLiked,
    bool clearFromYear = false,
    bool clearToYear = false,
  }) {
    emit(
      state.copyWith(
        minRating: minRating,
        fromYear: fromYear,
        toYear: toYear,
        onlyLiked: onlyLiked,
        clearFromYear: clearFromYear,
        clearToYear: clearToYear,
      ),
    );
  }

  Future<void> _persistRecentQuery(String query) async {
    final normalized = query.trim();
    if (normalized.length < 2) return;

    final updated = [
      normalized,
      ...state.recentQueries.where((item) => item != normalized),
    ].take(20).toList();

    emit(state.copyWith(recentQueries: updated));
    final prefs = await SharedPreferences.getInstance();
    await prefs.setStringList(_recentKey, updated);
  }

  @override
  Future<void> close() {
    _debounce?.cancel();
    return super.close();
  }
}
