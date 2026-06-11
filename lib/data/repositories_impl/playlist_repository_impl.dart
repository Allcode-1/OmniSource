import 'package:dio/dio.dart';
import '../../core/utils/app_logger.dart';
import '../../domain/entities/unified_content.dart';
import '../../domain/repositories/playlist_repository.dart';
import '../models/content_model.dart';
import '../models/playlist_model.dart';
import '../../core/constants/api_constants.dart';

class PlaylistRepositoryImpl implements PlaylistRepository {
  final Dio _dio;
  PlaylistRepositoryImpl(this._dio);

  @override
  Future<List<PlaylistModel>> getPlaylists() async {
    try {
      final response = await _dio.get(ApiConstants.playlists);
      return (response.data as List)
          .map((item) => PlaylistModel.fromJson(item))
          .toList();
    } catch (e, st) {
      AppLogger.error(
        'Get playlists failed',
        error: e,
        stackTrace: st,
        name: 'PlaylistRepository',
      );
      rethrow;
    }
  }

  @override
  Future<PlaylistModel> createPlaylist(
    String title, {
    String? description,
  }) async {
    try {
      final response = await _dio.post(
        ApiConstants.playlists,
        queryParameters: <String, dynamic>{
          'title': title,
          'description': description,
        }..removeWhere((_, value) => value == null),
      );
      return PlaylistModel.fromJson(response.data);
    } catch (e, st) {
      AppLogger.error(
        'Create playlist failed',
        error: e,
        stackTrace: st,
        name: 'PlaylistRepository',
      );
      rethrow;
    }
  }

  @override
  Future<PlaylistModel> updatePlaylist(
    String id, {
    String? title,
    String? description,
  }) async {
    try {
      final response = await _dio.patch(
        '${ApiConstants.playlists}/$id',
        data: <String, dynamic>{'title': title, 'description': description}
          ..removeWhere((_, value) => value == null),
      );
      return PlaylistModel.fromJson(response.data);
    } catch (e, st) {
      AppLogger.error(
        'Update playlist failed',
        error: e,
        stackTrace: st,
        name: 'PlaylistRepository',
      );
      rethrow;
    }
  }

  @override
  Future<void> deletePlaylist(String id) async {
    try {
      await _dio.delete('${ApiConstants.playlists}/$id');
    } catch (e, st) {
      AppLogger.error(
        'Delete playlist failed',
        error: e,
        stackTrace: st,
        name: 'PlaylistRepository',
      );
      rethrow;
    }
  }

  @override
  Future<void> addToPlaylist(String playlistId, UnifiedContent content) async {
    try {
      await _dio.post(
        '${ApiConstants.playlists}/$playlistId/add',
        data: ContentModel.fromEntity(content).toJson(),
      );
    } catch (e, st) {
      AppLogger.error(
        'Add to playlist failed',
        error: e,
        stackTrace: st,
        name: 'PlaylistRepository',
      );
      rethrow;
    }
  }

  @override
  Future<void> removeFromPlaylist(String playlistId, String contentRef) async {
    try {
      final encodedRef = Uri.encodeComponent(contentRef);
      await _dio.delete(
        '${ApiConstants.playlists}/$playlistId/remove/$encodedRef',
      );
    } catch (e, st) {
      AppLogger.error(
        'Remove from playlist failed',
        error: e,
        stackTrace: st,
        name: 'PlaylistRepository',
      );
      rethrow;
    }
  }

  @override
  Future<List<UnifiedContent>> getPlaylistContent(String playlistId) async {
    try {
      final response = await _dio.get('${ApiConstants.playlists}/$playlistId');
      final data = response.data;
      final List itemsRaw = data is Map ? (data['items'] as List? ?? []) : [];
      return itemsRaw.map((item) {
        if (item is Map && item['ext_id'] != null) {
          item['external_id'] = item['ext_id'];
        }
        return ContentModel.fromJson(item);
      }).toList();
    } catch (e, st) {
      AppLogger.error(
        'Get playlist content failed',
        error: e,
        stackTrace: st,
        name: 'PlaylistRepository',
      );
      rethrow;
    }
  }
}
