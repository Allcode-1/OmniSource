import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/utils/content_display.dart';

import '../../../domain/entities/unified_content.dart';
import '../../../domain/repositories/user_repository.dart';
import '../../bloc/auth/auth_cubit.dart';
import '../../bloc/auth/auth_state.dart';
import '../../bloc/library/library_cubit.dart';
import '../../bloc/library/library_state.dart';
import '../../bloc/search/search_cubit.dart';
import '../../bloc/search/search_state.dart';
import '../../widgets/app_feedback.dart';
import '../../widgets/user_avatar.dart';
import '../profile/profile_screen.dart';
import 'search_grid_card.dart';

class SearchScreen extends StatefulWidget {
  const SearchScreen({super.key});

  @override
  State<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends State<SearchScreen> {
  final ScrollController _scrollController = ScrollController();
  final TextEditingController _searchController = TextEditingController();
  final FocusNode _focusNode = FocusNode();

  double _appBarOpacity = 1.0;

  @override
  void initState() {
    super.initState();
    context.read<LibraryCubit>().loadLibraryData();

    _scrollController.addListener(() {
      final newOpacity = (1.0 - (_scrollController.offset / 80)).clamp(
        0.0,
        1.0,
      );
      if (newOpacity != _appBarOpacity) {
        setState(() => _appBarOpacity = newOpacity);
      }
    });

    _focusNode.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _scrollController.dispose();
    _searchController.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.appBackground,
      body: BlocBuilder<SearchCubit, SearchState>(
        builder: (context, state) {
          final libraryState = context.watch<LibraryCubit>().state;
          final likedIds = libraryState is LibraryLoaded
              ? libraryState.favorites
                    .map((item) => '${item.type}:${item.externalId}')
                    .toSet()
              : <String>{};
          final filtered = _applyAdvancedFilters(
            state.results,
            state,
            likedIds,
          );
          final displayResults = groupMusicAlbums(filtered);

          return Stack(
            children: [
              CustomScrollView(
                controller: _scrollController,
                physics: const BouncingScrollPhysics(),
                slivers: [
                  SliverToBoxAdapter(
                    child: SizedBox(
                      height: MediaQuery.paddingOf(context).top + 76,
                    ),
                  ),

                  SliverToBoxAdapter(
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 20),
                      child: _buildSearchBar(context),
                    ),
                  ),

                  const SliverToBoxAdapter(child: SizedBox(height: 12)),

                  SliverToBoxAdapter(
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 20),
                      child: _buildFilters(context, state.activeType),
                    ),
                  ),

                  const SliverToBoxAdapter(child: SizedBox(height: 14)),

                  if (_searchController.text.isEmpty &&
                      (state.recentQueries.isNotEmpty ||
                          state.savedQueries.isNotEmpty))
                    _buildSearchHistory(context, state),

                  if (state.isLoading)
                    const OmniGridSkeletonSliver()
                  else if (state.errorMessage.isNotEmpty)
                    SliverFillRemaining(
                      hasScrollBody: false,
                      child: OmniErrorState(
                        message: state.errorMessage,
                        onRetry: _searchController.text.trim().length < 2
                            ? null
                            : () => context.read<SearchCubit>().search(
                                _searchController.text,
                              ),
                      ),
                    )
                  else if (displayResults.isEmpty)
                    _buildEmptyState(
                      _searchController.text.isEmpty,
                      state.activeType,
                    )
                  else
                    SliverPadding(
                      padding: const EdgeInsets.symmetric(horizontal: 20),
                      sliver: SliverGrid(
                        gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                          crossAxisCount: 2,
                          crossAxisSpacing: 14,
                          mainAxisSpacing: 18,
                          childAspectRatio: _gridAspectRatio(state.activeType),
                        ),
                        delegate: SliverChildBuilderDelegate((context, index) {
                          final cluster = displayResults[index];
                          return SearchGridCard(
                            item: cluster.primary,
                            groupedItems: cluster.items,
                          );
                        }, childCount: displayResults.length),
                      ),
                    ),

                  const SliverToBoxAdapter(child: SizedBox(height: 100)),
                ],
              ),

              Positioned(
                top: 0,
                left: 0,
                right: 0,
                child: Opacity(
                  opacity: _appBarOpacity,
                  child: _buildAppBar(context),
                ),
              ),
            ],
          );
        },
      ),
    );
  }

  Widget _buildAppBar(BuildContext context) {
    return BlocBuilder<AuthCubit, AuthState>(
      builder: (context, authState) {
        final username = authState is AuthAuthenticated
            ? authState.user.username
            : "U";

        return Container(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [
                AppTheme.appBackground.withValues(alpha: 0.96),
                Colors.transparent,
              ],
            ),
          ),
          child: SafeArea(
            bottom: false,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(20, 14, 20, 10),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    "Search",
                    style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                      fontSize: 24,
                      fontWeight: FontWeight.w600,
                      height: 1.12,
                    ),
                  ),
                  UserAvatar(
                    username: username,
                    size: 38,
                    onTap: () {
                      final userRepository = context.read<UserRepository>();
                      Navigator.push(
                        context,
                        CupertinoPageRoute(
                          builder: (_) =>
                              ProfileScreen(userRepository: userRepository),
                        ),
                      );
                    },
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildSearchBar(BuildContext context) {
    return AnimatedContainer(
      duration: const Duration(milliseconds: 150),
      height: 52,
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: _focusNode.hasFocus
              ? AppTheme.primary
              : AppTheme.ink.withValues(alpha: 0.08),
          width: 1.4,
        ),
        boxShadow: [
          if (_focusNode.hasFocus)
            BoxShadow(
              color: AppTheme.primary.withValues(alpha: 0.18),
              blurRadius: 12,
              spreadRadius: 1,
            ),
        ],
      ),
      child: CupertinoSearchTextField(
        controller: _searchController,
        focusNode: _focusNode,
        backgroundColor: Colors.transparent,
        borderRadius: BorderRadius.circular(14),
        itemColor: AppTheme.ink.withValues(alpha: 0.7),
        style: const TextStyle(color: AppTheme.ink, fontSize: 15),
        placeholderStyle: TextStyle(
          color: AppTheme.ink.withValues(alpha: 0.5),
          fontSize: 15,
        ),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
        prefixIcon: const Icon(
          CupertinoIcons.search,
          color: AppTheme.secondary,
          size: 18,
        ),
        suffixIcon: const Icon(
          CupertinoIcons.xmark_circle_fill,
          color: AppTheme.secondary,
          size: 16,
        ),
        placeholder: "Artists, movies, books",
        onSuffixTap: () {
          _searchController.clear();
          context.read<SearchCubit>().search('');
          setState(() {});
        },
        onChanged: (val) {
          context.read<SearchCubit>().search(val);
          setState(() {});
        },
      ),
    );
  }

  Widget _buildFilters(BuildContext context, String activeType) {
    final filters = [
      {'label': 'Music', 'value': 'music'},
      {'label': 'Movies', 'value': 'movie'},
      {'label': 'Books', 'value': 'book'},
    ];

    return SizedBox(
      height: 36,
      child: ListView.builder(
        scrollDirection: Axis.horizontal,
        itemCount: filters.length,
        itemBuilder: (context, index) {
          final isSelected = activeType == filters[index]['value'];

          return Padding(
            padding: const EdgeInsets.only(right: 10),
            child: GestureDetector(
              onTap: () => context.read<SearchCubit>().setFilter(
                filters[index]['value']!,
                _searchController.text,
              ),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 180),
                padding: const EdgeInsets.symmetric(horizontal: 18),
                decoration: BoxDecoration(
                  color: isSelected ? AppTheme.primary : AppTheme.surface,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(
                    color: isSelected
                        ? AppTheme.primary
                        : AppTheme.ink.withValues(alpha: 0.06),
                  ),
                ),
                alignment: Alignment.center,
                child: Text(
                  filters[index]['label']!,
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: isSelected
                        ? Colors.white
                        : AppTheme.ink.withValues(alpha: 0.84),
                  ),
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildSearchHistory(BuildContext context, SearchState state) {
    return SliverToBoxAdapter(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (state.savedQueries.isNotEmpty) ...[
              const Text(
                'Saved Searches',
                style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 6),
              ...state.savedQueries.take(6).map((query) {
                return _HistoryQueryRow(
                  icon: CupertinoIcons.bookmark_fill,
                  query: query,
                  onTap: () {
                    _searchController.text = query;
                    context.read<SearchCubit>().search(query);
                    setState(() {});
                  },
                  onRemove: () =>
                      context.read<SearchCubit>().removeSavedQuery(query),
                );
              }),
              const SizedBox(height: 20),
            ],
            if (state.recentQueries.isNotEmpty) ...[
              Row(
                children: [
                  const Text(
                    'Recent Searches',
                    style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700),
                  ),
                  const Spacer(),
                  GestureDetector(
                    behavior: HitTestBehavior.opaque,
                    onTap: () =>
                        context.read<SearchCubit>().clearRecentQueries(),
                    child: const Padding(
                      padding: EdgeInsets.symmetric(vertical: 8),
                      child: Text(
                        'Clear',
                        style: TextStyle(
                          color: AppTheme.primary,
                          fontSize: 14,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 6),
              ...state.recentQueries.take(6).map((query) {
                return _HistoryQueryRow(
                  icon: CupertinoIcons.time,
                  query: query,
                  onTap: () {
                    _searchController.text = query;
                    context.read<SearchCubit>().search(query);
                    setState(() {});
                  },
                  onRemove: () =>
                      context.read<SearchCubit>().removeRecentQuery(query),
                );
              }),
              const SizedBox(height: 10),
            ],
          ],
        ),
      ),
    );
  }

  List<UnifiedContent> _applyAdvancedFilters(
    List<UnifiedContent> source,
    SearchState state,
    Set<String> likedIds,
  ) {
    return source.where((item) {
      if (item.rating < state.minRating) return false;
      if (state.onlyLiked &&
          !likedIds.contains('${item.type}:${item.externalId}')) {
        return false;
      }

      final release = item.releaseDate;
      int? year;
      if (release != null && release.isNotEmpty) {
        final value = release.length >= 4 ? release.substring(0, 4) : release;
        year = int.tryParse(value);
      }

      if (state.fromYear != null && year != null && year < state.fromYear!) {
        return false;
      }
      if (state.toYear != null && year != null && year > state.toYear!) {
        return false;
      }
      return true;
    }).toList();
  }

  Widget _buildEmptyState(bool isInitial, String activeType) {
    return SliverFillRemaining(
      hasScrollBody: false,
      child: OmniEmptyState(
        icon: isInitial ? Icons.search : Icons.tune,
        title: isInitial ? 'Find your next favorite' : 'No matches found',
        subtitle: isInitial
            ? _initialEmptySubtitle(activeType)
            : 'Try another query or switch the content type.',
      ),
    );
  }

  double _gridAspectRatio(String activeType) {
    return contentGridAspectRatio(activeType);
  }

  String _initialEmptySubtitle(String activeType) {
    switch (activeType) {
      case 'movie':
        return 'Search movies and cinematic picks.';
      case 'book':
        return 'Search books and authors.';
      default:
        return 'Search songs, albums, and artists.';
    }
  }
}

class _HistoryQueryRow extends StatelessWidget {
  final IconData icon;
  final String query;
  final VoidCallback onTap;
  final VoidCallback onRemove;

  const _HistoryQueryRow({
    required this.icon,
    required this.query,
    required this.onTap,
    required this.onRemove,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 12),
        decoration: BoxDecoration(
          border: Border(
            bottom: BorderSide(color: AppTheme.ink.withValues(alpha: 0.08)),
          ),
        ),
        child: Row(
          children: [
            Icon(icon, color: AppTheme.ink.withValues(alpha: 0.5), size: 21),
            const SizedBox(width: 14),
            Expanded(
              child: Text(
                query,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  color: AppTheme.ink,
                  fontSize: 15,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
            const SizedBox(width: 10),
            GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTap: onRemove,
              child: Padding(
                padding: const EdgeInsets.all(4),
                child: Icon(
                  CupertinoIcons.xmark_circle_fill,
                  color: AppTheme.ink.withValues(alpha: 0.34),
                  size: 18,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
