class ContentPreview {
  final String contentType;
  final String externalId;
  final String provider;
  final String previewType;
  final String title;
  final String url;
  final String? embedUrl;
  final String? externalUrl;
  final bool isPlayable;

  const ContentPreview({
    required this.contentType,
    required this.externalId,
    required this.provider,
    required this.previewType,
    required this.title,
    required this.url,
    this.embedUrl,
    this.externalUrl,
    this.isPlayable = true,
  });
}
