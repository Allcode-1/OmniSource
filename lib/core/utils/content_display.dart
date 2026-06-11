import '../../domain/entities/unified_content.dart';

class ContentCluster {
  final UnifiedContent primary;
  final List<UnifiedContent> items;

  const ContentCluster({required this.primary, required this.items});

  bool get isMusicAlbumGroup => primary.type == 'music' && items.length > 1;

  int get trackCount => items.length;

  String get displayTitle {
    if (isMusicAlbumGroup) {
      return contentAlbumTitle(primary) ?? primary.title;
    }
    return primary.title;
  }

  String displaySubtitle({bool showType = false}) {
    if (isMusicAlbumGroup) {
      final artist = contentArtistName(primary);
      final count = '$trackCount tracks';
      if (artist == null || artist.isEmpty) return count;
      return '$artist - $count';
    }

    final parts = <String>[];
    if (showType) parts.add(contentTypeLabel(primary.type));
    final subtitle = primary.subtitle?.trim();
    if (subtitle != null && subtitle.isNotEmpty) {
      parts.add(subtitle);
    } else if ((primary.releaseDate ?? '').trim().isNotEmpty) {
      parts.add(primary.releaseDate!.trim());
    }
    if (primary.rating > 0) parts.add(primary.rating.toStringAsFixed(1));
    return parts.take(2).join(' - ');
  }
}

List<ContentCluster> groupMusicAlbums(List<UnifiedContent> source) {
  final ordered = <ContentCluster>[];
  final grouped = <String, List<UnifiedContent>>{};
  final ungroupedByIndex = <int, UnifiedContent>{};

  for (var index = 0; index < source.length; index++) {
    final item = source[index];
    if (item.type != 'music') {
      ungroupedByIndex[index] = item;
      continue;
    }

    final key = _musicAlbumKey(item);
    if (key == null) {
      ungroupedByIndex[index] = item;
      continue;
    }
    grouped.putIfAbsent(key, () => []).add(item);
  }

  final emittedKeys = <String>{};
  for (var index = 0; index < source.length; index++) {
    final item = source[index];
    final key = item.type == 'music' ? _musicAlbumKey(item) : null;
    if (key == null) {
      final ungrouped = ungroupedByIndex[index];
      if (ungrouped != null) {
        ordered.add(ContentCluster(primary: ungrouped, items: [ungrouped]));
      }
      continue;
    }

    if (!emittedKeys.add(key)) continue;
    final items = grouped[key] ?? [item];
    ordered.add(ContentCluster(primary: items.first, items: items));
  }

  return ordered;
}

String? contentAlbumTitle(UnifiedContent item) {
  final direct = item.albumTitle?.trim();
  if (direct != null && direct.isNotEmpty) return direct;

  final description = item.description ?? '';
  final marker = RegExp(r'Album:\s*(.+)$', caseSensitive: false);
  final match = marker.firstMatch(description);
  final parsed = match?.group(1)?.trim();
  return parsed == null || parsed.isEmpty ? null : parsed;
}

String? contentArtistName(UnifiedContent item) {
  final direct = item.artistName?.trim();
  if (direct != null && direct.isNotEmpty) return direct;
  final subtitle = item.subtitle?.trim();
  return subtitle == null || subtitle.isEmpty ? null : subtitle;
}

String contentTypeLabel(String type) {
  switch (type) {
    case 'movie':
      return 'Movie';
    case 'book':
      return 'Book';
    case 'music':
      return 'Music';
    default:
      return 'Content';
  }
}

double contentGridAspectRatio(String type) {
  switch (type) {
    case 'movie':
      return 0.53;
    case 'book':
      return 0.55;
    case 'music':
      return 0.72;
    default:
      return 0.56;
  }
}

String? _musicAlbumKey(UnifiedContent item) {
  final albumId = item.albumId?.trim();
  if (albumId != null && albumId.isNotEmpty) return 'album:$albumId';

  final title = contentAlbumTitle(item)?.toLowerCase();
  final artist = contentArtistName(item)?.toLowerCase();
  final image = item.imageUrl?.trim().toLowerCase();
  if ((title == null || title.isEmpty) && (image == null || image.isEmpty)) {
    return null;
  }
  return [artist ?? '', title ?? '', image ?? ''].join('|');
}
