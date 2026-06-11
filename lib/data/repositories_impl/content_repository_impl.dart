import 'package:omnisource/data/models/playlist_model.dart';

import '../../core/utils/app_logger.dart';
import '../../domain/entities/content_preview.dart';
import '../../domain/entities/unified_content.dart';
import '../../domain/repositories/content_repository.dart';
import '../models/content_model.dart';
import '../models/content_preview_model.dart';
import '../../core/constants/api_constants.dart';
import 'package:dio/dio.dart';

class ContentRepositoryImpl implements ContentRepository {
  final Dio _dio;
  ContentRepositoryImpl(this._dio);

  Map<String, dynamic>? _typeQueryParameters(String? type) {
    if (type == null) return null;
    return {'type': type};
  }

  @override
  Future<Map<String, List<UnifiedContent>>> getHomeData({String? type}) async {
    try {
      final response = await _dio.get(
        ApiConstants.home,
        queryParameters: _typeQueryParameters(type),
      );

      final Map<String, dynamic> data = Map<String, dynamic>.from(
        response.data as Map,
      );
      return data.map(
        (key, value) => MapEntry(
          key,
          (value as List).map((i) => ContentModel.fromJson(i)).toList(),
        ),
      );
    } catch (e, st) {
      AppLogger.error(
        'Home data request failed',
        error: e,
        stackTrace: st,
        name: 'ContentRepository',
      );
      rethrow;
    }
  }

  @override
  Future<List<UnifiedContent>> getRecommendations({String? type}) async {
    try {
      final response = await _dio.get(
        ApiConstants.recommendations,
        queryParameters: _typeQueryParameters(type),
      );
      return (response.data as List)
          .map((i) => ContentModel.fromJson(i))
          .toList();
    } catch (e, st) {
      AppLogger.error(
        'Recommendations request failed',
        error: e,
        stackTrace: st,
        name: 'ContentRepository',
      );
      rethrow;
    }
  }

  @override
  Future<List<UnifiedContent>> search(String query, {String? type}) async {
    try {
      final response = await _dio.get(
        ApiConstants.search,
        queryParameters: <String, dynamic>{'query': query, 'type': type}
          ..removeWhere((_, value) => value == null),
      );
      return (response.data as List)
          .map((item) => ContentModel.fromJson(item))
          .toList();
    } catch (e, st) {
      AppLogger.error(
        'Search request failed',
        error: e,
        stackTrace: st,
        name: 'ContentRepository',
      );
      rethrow;
    }
  }

  @override
  Future<void> toggleLike(UnifiedContent item) async {
    try {
      await _dio.post(
        ApiConstants.like,
        data: ContentModel.fromEntity(item).toJson(),
      );
    } catch (e, st) {
      AppLogger.error(
        'Toggle like failed',
        error: e,
        stackTrace: st,
        name: 'ContentRepository',
      );
      rethrow;
    }
  }

  @override
  Future<List<UnifiedContent>> getFavorites({String? type}) async {
    try {
      final response = await _dio.get(
        ApiConstants.favorites,
        queryParameters: _typeQueryParameters(type),
      );

      return (response.data as List).map((item) {
        if (item is Map && item['ext_id'] != null) {
          item['external_id'] = item['ext_id'];
        }
        return ContentModel.fromJson(item);
      }).toList();
    } catch (e, st) {
      AppLogger.error(
        'Favorites request failed',
        error: e,
        stackTrace: st,
        name: 'ContentRepository',
      );
      rethrow;
    }
  }

  @override
  Future<List<UnifiedContent>> getTrending({String? type}) async {
    try {
      final response = await _dio.get(
        ApiConstants.trending,
        queryParameters: _typeQueryParameters(type),
      );
      return (response.data as List)
          .map((i) => ContentModel.fromJson(i))
          .toList();
    } catch (e, st) {
      AppLogger.error(
        'Trending request failed',
        error: e,
        stackTrace: st,
        name: 'ContentRepository',
      );
      rethrow;
    }
  }

  @override
  Future<List<UnifiedContent>> getDiscovery(String tag) async {
    try {
      final response = await _dio.get(
        '/content/discover',
        queryParameters: {'tag': tag},
      );
      return (response.data as List)
          .map((i) => ContentModel.fromJson(i))
          .toList();
    } catch (e, st) {
      AppLogger.error(
        'Discovery request failed',
        error: e,
        stackTrace: st,
        name: 'ContentRepository',
      );
      rethrow;
    }
  }

  @override
  Future<List<UnifiedContent>> getDeepResearch(
    String tag, {
    String? type,
  }) async {
    try {
      final response = await _dio.get(
        ApiConstants.deepResearch,
        queryParameters: <String, dynamic>{'tag': tag, 'type': type}
          ..removeWhere((_, value) => value == null),
      );
      return (response.data as List)
          .map((item) => ContentModel.fromJson(item))
          .toList();
    } catch (e, st) {
      AppLogger.error(
        'Deep research request failed',
        error: e,
        stackTrace: st,
        name: 'ContentRepository',
      );
      rethrow;
    }
  }

  @override
  Future<ContentPreview?> getPreview(UnifiedContent item) async {
    try {
      final response = await _dio.get(
        ApiConstants.preview,
        queryParameters: <String, dynamic>{
          'type': item.type,
          'external_id': item.externalId,
          'title': item.title,
          'subtitle': item.subtitle,
        }..removeWhere((_, value) => value == null),
      );
      return ContentPreviewModel.fromJson(response.data);
    } on DioException catch (e, st) {
      if (e.response?.statusCode == 404) return null;
      AppLogger.error(
        'Preview request failed',
        error: e,
        stackTrace: st,
        name: 'ContentRepository',
      );
      rethrow;
    } catch (e, st) {
      AppLogger.error(
        'Preview request failed',
        error: e,
        stackTrace: st,
        name: 'ContentRepository',
      );
      rethrow;
    }
  }

  @override
  Future<List<PlaylistModel>> getPlaylists() async {
    try {
      final response = await _dio.get(ApiConstants.playlists);
      return (response.data as List)
          .map((item) => PlaylistModel.fromJson(item))
          .toList();
    } catch (e, st) {
      AppLogger.error(
        'Playlists request failed',
        error: e,
        stackTrace: st,
        name: 'ContentRepository',
      );
      rethrow;
    }
  }
}
