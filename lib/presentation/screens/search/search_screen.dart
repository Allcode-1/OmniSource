import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import '../../../core/theme/app_theme.dart';

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
                      state.recentQueries.isNotEmpty)
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
                  else if (filtered.isEmpty)
                    _buildEmptyState(_searchController.text.isEmpty)
                  else
                    SliverPadding(
                      padding: const EdgeInsets.symmetric(horizontal: 20),
                      sliver: SliverGrid(
                        gridDelegate:
                            const SliverGridDelegateWithFixedCrossAxisCount(
                              crossAxisCount: 2,
                              crossAxisSpacing: 14,
                              mainAxisSpacing: 18,
                              childAspectRatio: 0.63,
                            ),
                        delegate: SliverChildBuilderDelegate(
                          (context, index) =>
                              SearchGridCard(item: filtered[index]),
                          childCount: filtered.length,
                        ),
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
                Theme.of(context).colorScheme.surface.withValues(alpha: 0.96),
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
    final theme = Theme.of(context);
    return AnimatedContainer(
      duration: const Duration(milliseconds: 150),
      height: 52,
      decoration: BoxDecoration(
        color: theme.cardColor.withValues(alpha: 0.84),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: _focusNode.hasFocus
              ? AppTheme.primary
              : Colors.white.withValues(alpha: 0.08),
          width: 1.4,
        ),
        boxShadow: [
          if (_focusNode.hasFocus)
            BoxShadow(
              color: AppTheme.primary.withValues(alpha: 0.2),
              blurRadius: 12,
              spreadRadius: 1,
            ),
        ],
      ),
      child: CupertinoSearchTextField(
        controller: _searchController,
        focusNode: _focusNode,
        backgroundColor: theme.cardColor.withValues(alpha: 0.84),
        borderRadius: BorderRadius.circular(14),
        itemColor: Colors.white70,
        style: const TextStyle(color: Colors.white, fontSize: 15),
        placeholderStyle: const TextStyle(color: Colors.white54, fontSize: 15),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
        prefixIcon: const Icon(
          CupertinoIcons.search,
          color: Colors.white54,
          size: 18,
        ),
        suffixIcon: const Icon(
          CupertinoIcons.xmark_circle_fill,
          color: Colors.white30,
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
      {'label': 'All', 'value': 'all'},
      {'label': 'Movies', 'value': 'movie'},
      {'label': 'Music', 'value': 'music'},
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
                  color: isSelected
                      ? AppTheme.primary
                      : Theme.of(context).cardColor.withValues(alpha: 0.82),
                  borderRadius: BorderRadius.circular(20),
                ),
                alignment: Alignment.center,
                child: Text(
                  filters[index]['label']!,
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: Colors.white,
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
                style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: state.savedQueries.map((query) {
                  return InputChip(
                    label: Text(query),
                    onPressed: () {
                      _searchController.text = query;
                      context.read<SearchCubit>().search(query);
                      setState(() {});
                    },
                    onDeleted: () =>
                        context.read<SearchCubit>().removeSavedQuery(query),
                  );
                }).toList(),
              ),
              const SizedBox(height: 12),
            ],
            Row(
              children: [
                const Text(
                  'Recent Searches',
                  style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700),
                ),
                const Spacer(),
                TextButton(
                  onPressed: () =>
                      context.read<SearchCubit>().clearRecentQueries(),
                  child: const Text('Clear'),
                ),
              ],
            ),
            const SizedBox(height: 6),
            ...state.recentQueries.take(6).map((query) {
              return ListTile(
                dense: true,
                contentPadding: EdgeInsets.zero,
                leading: const Icon(CupertinoIcons.time),
                title: Text(query),
                onTap: () {
                  _searchController.text = query;
                  context.read<SearchCubit>().search(query);
                  setState(() {});
                },
              );
            }),
            const SizedBox(height: 10),
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

  Widget _buildEmptyState(bool isInitial) {
    return SliverFillRemaining(
      hasScrollBody: false,
      child: OmniEmptyState(
        icon: isInitial
            ? PhosphorIcons.magnifyingGlass(PhosphorIconsStyle.light)
            : PhosphorIcons.slidersHorizontal(PhosphorIconsStyle.light),
        title: isInitial ? 'Find your next favorite' : 'No matches found',
        subtitle: isInitial
            ? 'Search across movies, music, and books.'
            : 'Try another query or switch the content type.',
      ),
    );
  }
}
