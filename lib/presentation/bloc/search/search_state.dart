import '../../../domain/entities/unified_content.dart';

class SearchState {
  final List<UnifiedContent> results;
  final bool isLoading;
  final String activeType; // 'movie', 'music', 'book'
  final String errorMessage;
  final List<String> recentQueries;
  final List<String> savedQueries;
  final double minRating;
  final int? fromYear;
  final int? toYear;
  final bool onlyLiked;
  final String lastQuery;

  SearchState({
    this.results = const [],
    this.isLoading = false,
    this.activeType = 'music',
    this.errorMessage = '',
    this.recentQueries = const [],
    this.savedQueries = const [],
    this.minRating = 0.0,
    this.fromYear,
    this.toYear,
    this.onlyLiked = false,
    this.lastQuery = '',
  });

  SearchState copyWith({
    List<UnifiedContent>? results,
    bool? isLoading,
    String? activeType,
    String? errorMessage,
    List<String>? recentQueries,
    List<String>? savedQueries,
    double? minRating,
    int? fromYear,
    int? toYear,
    bool? onlyLiked,
    String? lastQuery,
    bool clearFromYear = false,
    bool clearToYear = false,
  }) {
    return SearchState(
      results: results ?? this.results,
      isLoading: isLoading ?? this.isLoading,
      activeType: activeType ?? this.activeType,
      errorMessage: errorMessage ?? this.errorMessage,
      recentQueries: recentQueries ?? this.recentQueries,
      savedQueries: savedQueries ?? this.savedQueries,
      minRating: minRating ?? this.minRating,
      fromYear: clearFromYear ? null : (fromYear ?? this.fromYear),
      toYear: clearToYear ? null : (toYear ?? this.toYear),
      onlyLiked: onlyLiked ?? this.onlyLiked,
      lastQuery: lastQuery ?? this.lastQuery,
    );
  }
}
