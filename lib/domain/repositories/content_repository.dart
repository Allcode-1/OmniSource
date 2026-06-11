import '../entities/unified_content.dart';
import '../entities/content_preview.dart';
import '../../data/models/playlist_model.dart';

abstract class ContentRepository {
  Future<List<UnifiedContent>> search(String query, {String? type});
  Future<void> toggleLike(UnifiedContent item);
  Future<List<UnifiedContent>> getFavorites({String? type});
  Future<Map<String, List<UnifiedContent>>> getHomeData({String? type});
  Future<List<UnifiedContent>> getTrending({String? type});
  Future<List<UnifiedContent>> getRecommendations({String? type});
  Future<List<UnifiedContent>> getDiscovery(String tag);
  Future<List<UnifiedContent>> getDeepResearch(String tag, {String? type});
  Future<ContentPreview?> getPreview(UnifiedContent item);
  Future<List<PlaylistModel>> getPlaylists();
}
