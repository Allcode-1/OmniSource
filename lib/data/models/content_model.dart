import '../../domain/entities/unified_content.dart';
import '../../core/constants/api_constants.dart';

class ContentModel extends UnifiedContent {
  ContentModel({
    required super.id,
    required super.externalId,
    required super.type,
    required super.title,
    super.subtitle,
    super.description,
    super.imageUrl,
    super.rating,
    super.genres,
    super.releaseDate,
    super.recommendationReason,
    super.albumId,
    super.albumTitle,
    super.artistName,
    super.previewUrl,
    super.externalUrl,
  });

  static String _asString(dynamic value, {String fallback = ''}) {
    if (value == null) return fallback;
    final result = value.toString();
    return result == 'null' ? fallback : result;
  }

  static double _asDouble(dynamic value, {double fallback = 0.0}) {
    if (value == null) return fallback;
    if (value is num) return value.toDouble();
    return double.tryParse(value.toString()) ?? fallback;
  }

  static List<String> _asStringList(dynamic value) {
    if (value is List) {
      return value
          .where((item) => item != null)
          .map((item) => item.toString())
          .toList();
    }
    if (value == null) return const [];
    return [value.toString()];
  }

  static String? _normalizeImageUrl(dynamic value) {
    final raw = _asString(value, fallback: '');
    if (raw.isEmpty) return null;

    return ApiConstants.resolveImageUrl(raw);
  }

  factory ContentModel.fromJson(dynamic json) {
    if (json == null || json is! Map) return ContentModel.empty();
    final map = Map<String, dynamic>.from(json);

    try {
      return ContentModel(
        id: _asString(map['_id'] ?? map['id']),
        externalId: _asString(map['ext_id'] ?? map['external_id']),
        type: _asString(map['type'], fallback: 'unknown'),
        title: _asString(map['title'], fallback: 'No Title'),
        subtitle: _asString(map['subtitle'], fallback: '').isEmpty
            ? null
            : _asString(map['subtitle']),
        description: _asString(map['description'], fallback: '').isEmpty
            ? null
            : _asString(map['description']),
        imageUrl: _normalizeImageUrl(map['image_url']),
        rating: _asDouble(map['rating']),
        genres: _asStringList(map['genres']),
        releaseDate: _asString(map['release_date'], fallback: '').isEmpty
            ? null
            : _asString(map['release_date']),
        recommendationReason:
            _asString(map['recommendation_reason'], fallback: '').isEmpty
            ? null
            : _asString(map['recommendation_reason']),
        albumId: _asString(map['album_id'], fallback: '').isEmpty
            ? null
            : _asString(map['album_id']),
        albumTitle: _asString(map['album_title'], fallback: '').isEmpty
            ? null
            : _asString(map['album_title']),
        artistName: _asString(map['artist_name'], fallback: '').isEmpty
            ? null
            : _asString(map['artist_name']),
        previewUrl: _asString(map['preview_url'], fallback: '').isEmpty
            ? null
            : _asString(map['preview_url']),
        externalUrl: _asString(map['external_url'], fallback: '').isEmpty
            ? null
            : _asString(map['external_url']),
      );
    } catch (_) {
      return ContentModel.empty();
    }
  }

  factory ContentModel.empty() {
    return ContentModel(
      id: '',
      externalId: '',
      type: 'unknown',
      title: 'Loading Error',
      genres: [],
    );
  }

  factory ContentModel.fromEntity(UnifiedContent entity) {
    return ContentModel(
      id: entity.id,
      externalId: entity.externalId,
      type: entity.type,
      title: entity.title,
      subtitle: entity.subtitle,
      description: entity.description,
      imageUrl: entity.imageUrl,
      rating: entity.rating,
      genres: entity.genres,
      releaseDate: entity.releaseDate,
      recommendationReason: entity.recommendationReason,
      albumId: entity.albumId,
      albumTitle: entity.albumTitle,
      artistName: entity.artistName,
      previewUrl: entity.previewUrl,
      externalUrl: entity.externalUrl,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      '_id': id,
      'ext_id': externalId,
      'type': type,
      'title': title,
      'subtitle': subtitle,
      'description': description,
      'image_url': imageUrl,
      'rating': rating,
      'genres': genres,
      'release_date': releaseDate,
      'recommendation_reason': recommendationReason,
      'album_id': albumId,
      'album_title': albumTitle,
      'artist_name': artistName,
      'preview_url': previewUrl,
      'external_url': externalUrl,
    };
  }
}
