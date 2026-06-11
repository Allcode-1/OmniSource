import '../../domain/entities/content_preview.dart';

class ContentPreviewModel extends ContentPreview {
  const ContentPreviewModel({
    required super.contentType,
    required super.externalId,
    required super.provider,
    required super.previewType,
    required super.title,
    required super.url,
    super.embedUrl,
    super.externalUrl,
    super.isPlayable,
  });

  factory ContentPreviewModel.fromJson(dynamic json) {
    final map = Map<String, dynamic>.from(json as Map);
    return ContentPreviewModel(
      contentType: (map['content_type'] ?? '').toString(),
      externalId: (map['external_id'] ?? '').toString(),
      provider: (map['provider'] ?? '').toString(),
      previewType: (map['preview_type'] ?? '').toString(),
      title: (map['title'] ?? '').toString(),
      url: (map['url'] ?? '').toString(),
      embedUrl: _optionalString(map['embed_url']),
      externalUrl: _optionalString(map['external_url']),
      isPlayable: map['is_playable'] != false,
    );
  }

  static String? _optionalString(dynamic value) {
    if (value == null) return null;
    final result = value.toString().trim();
    return result.isEmpty ? null : result;
  }
}
