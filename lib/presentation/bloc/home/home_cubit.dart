import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../core/utils/app_logger.dart';
import '../../../domain/repositories/content_repository.dart';
import '../../../domain/entities/unified_content.dart';
import 'home_state.dart';

export 'home_state.dart';

enum ContentCategory { all, movie, music, book }

class HomeCubit extends Cubit<HomeState> {
  final ContentRepository repository;
  int _loadToken = 0;
  final Map<ContentCategory, HomeState> _stateCache = {};

  HomeCubit(this.repository)
    : super(HomeState(category: ContentCategory.music));

  void setCategory(ContentCategory category) {
    if (state.category == category) return;
    final cached = _stateCache[category];
    if (cached != null) {
      emit(cached.copyWith(category: category, isLoading: false, error: ''));
      loadContent(silent: true);
    } else {
      emit(state.copyWith(category: category, isLoading: true));
      loadContent();
    }
  }

  String _getCategoryType() {
    switch (state.category) {
      case ContentCategory.all:
        return 'all';
      case ContentCategory.movie:
        return 'movie';
      case ContentCategory.music:
        return 'music';
      case ContentCategory.book:
        return 'book';
    }
  }

  Future<void> loadContent({bool silent = false}) async {
    final token = ++_loadToken;
    if (!silent) {
      emit(state.copyWith(isLoading: true, error: ''));
    }

    try {
      final type = _getCategoryType();

      final results = await Future.wait([
        repository.getRecommendations(type: type),
        repository.getHomeData(type: type),
      ]);

      final recsList = results[0] as List<UnifiedContent>;
      final homeDataMap = results[1] as Map<String, List<UnifiedContent>>;
      if (isClosed || token != _loadToken) return;

      final finalTrending =
          homeDataMap['Trending Now'] ??
          homeDataMap['Trending'] ??
          _flattenHomeMap(homeDataMap);
      final recommendations = homeDataMap['For You'] ?? recsList;

      final nextState = state.copyWith(
        isLoading: false,
        trending: _dedupeContent(finalTrending),
        recommendations: _dedupeContent(recommendations),
        homeMap: _dedupeHomeMap(homeDataMap),
        error: '',
      );
      _stateCache[state.category] = nextState;
      emit(nextState);
    } catch (e, st) {
      AppLogger.error(
        'Home content loading failed',
        error: e,
        stackTrace: st,
        name: 'HomeCubit',
      );
      if (isClosed || token != _loadToken) return;
      emit(state.copyWith(error: "Ошибка загрузки: ${e.toString()}"));
    } finally {
      if (!isClosed && token == _loadToken && state.isLoading) {
        emit(state.copyWith(isLoading: false, error: state.error));
      }
    }
  }

  Future<void> toggleLike(UnifiedContent item) async {
    try {
      await repository.toggleLike(item);
    } catch (e, st) {
      AppLogger.error(
        'Toggle like failed in HomeCubit',
        error: e,
        stackTrace: st,
        name: 'HomeCubit',
      );
    }
  }

  List<UnifiedContent> _dedupeContent(List<UnifiedContent> items) {
    final seen = <String>{};
    final result = <UnifiedContent>[];

    for (final item in items) {
      final key = _contentKey(item);
      if (key.isEmpty || seen.contains(key)) continue;
      seen.add(key);
      result.add(item);
    }

    return result;
  }

  Map<String, List<UnifiedContent>> _dedupeHomeMap(
    Map<String, List<UnifiedContent>> source,
  ) {
    return source.map((key, value) => MapEntry(key, _dedupeContent(value)));
  }

  List<UnifiedContent> _flattenHomeMap(
    Map<String, List<UnifiedContent>> source,
  ) {
    return source.values.expand((items) => items).toList();
  }

  String _contentKey(UnifiedContent item) {
    final externalId = item.externalId.trim();
    if (externalId.isNotEmpty) return '${item.type}:$externalId';
    return '${item.type}:${item.id}';
  }
}
