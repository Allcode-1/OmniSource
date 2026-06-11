import 'package:omnisource/data/models/playlist_model.dart';
import 'package:omnisource/domain/entities/app_notification.dart';
import 'package:omnisource/domain/entities/content_preview.dart';
import 'package:omnisource/domain/entities/interaction_event.dart';
import 'package:omnisource/domain/entities/unified_content.dart';
import 'package:omnisource/domain/entities/usage_stats.dart';
import 'package:omnisource/domain/entities/user.dart';
import 'package:omnisource/domain/repositories/analytics_repository.dart';
import 'package:omnisource/domain/repositories/auth_repository.dart';
import 'package:omnisource/domain/repositories/content_repository.dart';
import 'package:omnisource/domain/repositories/playlist_repository.dart';

UnifiedContent makeContent({
  required String id,
  required String externalId,
  required String type,
  required String title,
  String? subtitle,
  double rating = 0,
}) {
  return UnifiedContent(
    id: id,
    externalId: externalId,
    type: type,
    title: title,
    subtitle: subtitle ?? type,
    imageUrl: 'https://img.test/$externalId.jpg',
    rating: rating,
    genres: const ['test'],
    releaseDate: '2024-01-01',
  );
}

class FakeContentRepository implements ContentRepository {
  List<UnifiedContent> searchResponse = const [];
  List<UnifiedContent> favoritesResponse = const [];
  List<UnifiedContent> trendingResponse = const [];
  List<UnifiedContent> recommendationsResponse = const [];
  List<UnifiedContent> discoveryResponse = const [];
  List<UnifiedContent> deepResearchResponse = const [];
  List<PlaylistModel> playlistsResponse = const [];
  ContentPreview? previewResponse;
  Map<String, List<UnifiedContent>> homeDataResponse = const {};

  Object? searchError;
  Object? favoritesError;
  Object? trendingError;
  Object? recommendationsError;
  Object? homeDataError;
  Object? toggleLikeError;
  Object? previewError;

  int searchCalls = 0;
  int favoritesCalls = 0;
  int trendingCalls = 0;
  int recommendationsCalls = 0;
  int homeDataCalls = 0;
  int toggleLikeCalls = 0;
  int previewCalls = 0;

  String? lastSearchType;
  String? lastSearchQuery;
  String? lastTrendingType;
  String? lastRecommendationsType;
  String? lastHomeType;
  UnifiedContent? lastToggledContent;
  UnifiedContent? lastPreviewContent;

  @override
  Future<List<UnifiedContent>> search(String query, {String? type}) async {
    searchCalls++;
    lastSearchQuery = query;
    lastSearchType = type;
    if (searchError != null) throw searchError!;
    return searchResponse;
  }

  @override
  Future<void> toggleLike(UnifiedContent item) async {
    toggleLikeCalls++;
    lastToggledContent = item;
    if (toggleLikeError != null) throw toggleLikeError!;
  }

  @override
  Future<List<UnifiedContent>> getFavorites({String? type}) async {
    favoritesCalls++;
    if (favoritesError != null) throw favoritesError!;
    return favoritesResponse;
  }

  @override
  Future<Map<String, List<UnifiedContent>>> getHomeData({String? type}) async {
    homeDataCalls++;
    lastHomeType = type;
    if (homeDataError != null) throw homeDataError!;
    return homeDataResponse;
  }

  @override
  Future<List<UnifiedContent>> getTrending({String? type}) async {
    trendingCalls++;
    lastTrendingType = type;
    if (trendingError != null) throw trendingError!;
    return trendingResponse;
  }

  @override
  Future<List<UnifiedContent>> getRecommendations({String? type}) async {
    recommendationsCalls++;
    lastRecommendationsType = type;
    if (recommendationsError != null) throw recommendationsError!;
    return recommendationsResponse;
  }

  @override
  Future<List<UnifiedContent>> getDiscovery(String tag) async {
    return discoveryResponse;
  }

  @override
  Future<List<UnifiedContent>> getDeepResearch(
    String tag, {
    String? type,
  }) async {
    return deepResearchResponse;
  }

  @override
  Future<ContentPreview?> getPreview(UnifiedContent item) async {
    previewCalls++;
    lastPreviewContent = item;
    if (previewError != null) throw previewError!;
    return previewResponse;
  }

  @override
  Future<List<PlaylistModel>> getPlaylists() async {
    return playlistsResponse;
  }
}

class FakePlaylistRepository implements PlaylistRepository {
  List<PlaylistModel> playlistsResponse = const [];
  final Map<String, List<UnifiedContent>> contentByPlaylistId = {};

  int getPlaylistsCalls = 0;
  int getPlaylistContentCalls = 0;
  int createCalls = 0;
  int updateCalls = 0;
  int deleteCalls = 0;
  int addCalls = 0;
  int removeCalls = 0;

  Object? getPlaylistsError;
  final Map<String, Object> playlistContentErrorById = {};

  String? lastCreatedTitle;
  String? lastUpdatedId;
  String? lastDeletedId;

  @override
  Future<List<PlaylistModel>> getPlaylists() async {
    getPlaylistsCalls++;
    if (getPlaylistsError != null) throw getPlaylistsError!;
    return playlistsResponse;
  }

  @override
  Future<PlaylistModel> createPlaylist(
    String title, {
    String? description,
  }) async {
    createCalls++;
    lastCreatedTitle = title;
    final created = PlaylistModel(
      id: 'created-$createCalls',
      title: title,
      description: description,
      items: const [],
    );
    playlistsResponse = [...playlistsResponse, created];
    return created;
  }

  @override
  Future<PlaylistModel> updatePlaylist(
    String id, {
    String? title,
    String? description,
  }) async {
    updateCalls++;
    lastUpdatedId = id;
    final existing = playlistsResponse.firstWhere((item) => item.id == id);
    final updated = PlaylistModel(
      id: existing.id,
      title: title ?? existing.title,
      description: description ?? existing.description,
      items: existing.items,
    );
    playlistsResponse = playlistsResponse
        .map((item) => item.id == id ? updated : item)
        .toList();
    return updated;
  }

  @override
  Future<void> deletePlaylist(String id) async {
    deleteCalls++;
    lastDeletedId = id;
    playlistsResponse = playlistsResponse
        .where((item) => item.id != id)
        .toList();
    contentByPlaylistId.remove(id);
  }

  @override
  Future<void> addToPlaylist(String playlistId, UnifiedContent content) async {
    addCalls++;
    final current = contentByPlaylistId[playlistId] ?? <UnifiedContent>[];
    contentByPlaylistId[playlistId] = [...current, content];
  }

  @override
  Future<void> removeFromPlaylist(String playlistId, String externalId) async {
    removeCalls++;
    final current = contentByPlaylistId[playlistId] ?? <UnifiedContent>[];
    contentByPlaylistId[playlistId] = current
        .where((item) => item.externalId != externalId)
        .toList();
  }

  @override
  Future<List<UnifiedContent>> getPlaylistContent(String playlistId) async {
    getPlaylistContentCalls++;
    final error = playlistContentErrorById[playlistId];
    if (error != null) throw error;
    return contentByPlaylistId[playlistId] ?? const [];
  }
}

class FakeAuthRepository implements AuthRepository {
  User? loginUser;
  User? registerUser;
  User? currentUser;

  Object? loginError;
  Object? registerError;
  Object? forgotPasswordError;
  Object? resetPasswordError;
  Object? logoutError;
  Object? checkAuthError;

  int loginCalls = 0;
  int registerCalls = 0;
  int getCurrentUserCalls = 0;
  int forgotPasswordCalls = 0;
  int resetPasswordCalls = 0;
  int logoutCalls = 0;
  int completeOnboardingCalls = 0;

  List<String> lastOnboardingTags = const [];

  @override
  Future<User> login(String email, String password) async {
    loginCalls++;
    if (loginError != null) throw loginError!;
    return loginUser!;
  }

  @override
  Future<User> register(String email, String password, String username) async {
    registerCalls++;
    if (registerError != null) throw registerError!;
    return registerUser!;
  }

  @override
  Future<User?> getCurrentUser() async {
    getCurrentUserCalls++;
    return currentUser;
  }

  @override
  Future<List<String>> getAvailableTags() async {
    return const ['action', 'noir'];
  }

  @override
  Future<void> completeOnboarding(List<String> tags) async {
    completeOnboardingCalls++;
    lastOnboardingTags = tags;
  }

  @override
  Future<void> forgotPassword(String email) async {
    forgotPasswordCalls++;
    if (forgotPasswordError != null) throw forgotPasswordError!;
  }

  @override
  Future<void> resetPassword(String token, String newPassword) async {
    resetPasswordCalls++;
    if (resetPasswordError != null) throw resetPasswordError!;
  }

  @override
  Future<void> logout() async {
    logoutCalls++;
    if (logoutError != null) throw logoutError!;
  }

  @override
  Future<bool> checkAuth() async {
    if (checkAuthError != null) throw checkAuthError!;
    return currentUser != null;
  }
}

class FakeAnalyticsRepository implements AnalyticsRepository {
  final List<Map<String, dynamic>> trackedEvents = [];
  String rankingVariant = 'hybrid_ml';
  final List<String> offlineQueue = [];

  @override
  Future<void> trackEvent({
    required String type,
    String? extId,
    String? contentType,
    double? weight,
    Map<String, dynamic>? meta,
  }) async {
    trackedEvents.add({
      'type': type,
      'extId': extId,
      'contentType': contentType,
      'weight': weight,
      'meta': meta ?? <String, dynamic>{},
    });
  }

  @override
  Future<List<InteractionEvent>> getTimeline({int limit = 50}) async {
    return const [];
  }

  @override
  Future<UsageStats> getStats({int days = 30}) async {
    return UsageStats(
      totalEvents: 0,
      countsByType: const {},
      ctr: 0,
      saveRate: 0,
      avgDwellSeconds: 0,
      topContentTypes: const {},
      abMetrics: const {},
    );
  }

  @override
  Future<List<AppNotification>> getNotifications() async {
    return const [];
  }

  @override
  Future<String> getRankingVariant() async {
    return rankingVariant;
  }

  @override
  Future<String> setRankingVariant(String variant) async {
    rankingVariant = variant;
    return rankingVariant;
  }

  @override
  Future<void> enqueueOfflineTask(String task) async {
    offlineQueue.add(task);
  }

  @override
  Future<List<String>> getOfflineQueue() async {
    return List<String>.from(offlineQueue);
  }

  @override
  Future<void> clearOfflineQueue() async {
    offlineQueue.clear();
  }
}
