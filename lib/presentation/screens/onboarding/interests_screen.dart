import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../../core/theme/app_theme.dart';
import '../../../domain/repositories/auth_repository.dart';
import '../../bloc/auth/auth_cubit.dart';
import '../../bloc/auth/auth_state.dart';

class InterestsSelectionScreen extends StatefulWidget {
  const InterestsSelectionScreen({super.key});

  @override
  State<InterestsSelectionScreen> createState() =>
      _InterestsSelectionScreenState();
}

class _InterestsSelectionScreenState extends State<InterestsSelectionScreen> {
  static const _fallbackTags = [
    'action',
    'adventure',
    'anime',
    'chill',
    'comedy',
    'crime',
    'cyberpunk',
    'dark',
    'drama',
    'epic',
    'fantasy',
    'history',
    'horror',
    'magic',
    'mystery',
    'noir',
    'retro',
    'romance',
    'sci-fi',
    'space',
    'thriller',
  ];

  final Set<String> _selectedTags = {};
  final TextEditingController _searchController = TextEditingController();

  List<String> _allTags = const [];
  List<String> _filteredTags = const [];
  bool _isLoading = true;
  String _tagLoadIssue = '';

  @override
  void initState() {
    super.initState();
    _searchController.addListener(_filterTags);
    _loadTags();
  }

  @override
  void dispose() {
    _searchController.removeListener(_filterTags);
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _loadTags() async {
    setState(() {
      _isLoading = true;
      _tagLoadIssue = '';
    });

    try {
      final tags = await context.read<AuthRepository>().getAvailableTags();
      final normalized = _normalizeTags(tags);
      if (!mounted) return;
      setState(() {
        _allTags = normalized.isEmpty ? _fallbackTags : normalized;
        _filteredTags = _allTags;
        _tagLoadIssue = normalized.isEmpty
            ? 'Starter interests loaded while the backend catches up.'
            : '';
        _isLoading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _allTags = _fallbackTags;
        _filteredTags = _fallbackTags;
        _tagLoadIssue =
            'Starter interests loaded while the backend catches up.';
        _isLoading = false;
      });
    }
  }

  List<String> _normalizeTags(List<String> tags) {
    final seen = <String>{};
    final normalized = <String>[];
    for (final tag in tags) {
      final value = tag.trim().toLowerCase();
      if (value.isEmpty || seen.contains(value)) continue;
      seen.add(value);
      normalized.add(value);
    }
    normalized.sort();
    return normalized;
  }

  void _filterTags() {
    final query = _searchController.text.trim().toLowerCase();
    setState(() {
      _filteredTags = query.isEmpty
          ? _allTags
          : _allTags.where((tag) => tag.contains(query)).toList();
    });
  }

  void _toggleTag(String tag) {
    setState(() {
      if (_selectedTags.contains(tag)) {
        _selectedTags.remove(tag);
      } else {
        _selectedTags.add(tag);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return BlocConsumer<AuthCubit, AuthState>(
      listener: (context, state) {
        if (state is AuthOnboardingFailure) {
          ScaffoldMessenger.of(
            context,
          ).showSnackBar(SnackBar(content: Text(state.message)));
        }
      },
      builder: (context, authState) {
        final isSaving = authState is AuthOnboardingSaving;

        return Scaffold(
          backgroundColor: AppTheme.appBackground,
          body: SafeArea(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _Header(selectedCount: _selectedTags.length),
                Padding(
                  padding: const EdgeInsets.fromLTRB(20, 6, 20, 0),
                  child: _SearchField(controller: _searchController),
                ),
                if (_tagLoadIssue.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.fromLTRB(20, 12, 20, 0),
                    child: _SubtleNotice(text: _tagLoadIssue),
                  ),
                Expanded(
                  child: AnimatedSwitcher(
                    duration: const Duration(milliseconds: 180),
                    child: _isLoading
                        ? const _LoadingInterests()
                        : _buildTagContent(),
                  ),
                ),
                _BottomAction(
                  selectedCount: _selectedTags.length,
                  isSaving: isSaving,
                  onSubmit: () => context.read<AuthCubit>().completeOnboarding(
                    _selectedTags.toList(),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildTagContent() {
    if (_filteredTags.isEmpty) {
      return _EmptyInterests(
        query: _searchController.text,
        onClear: () => _searchController.clear(),
      );
    }

    return CustomScrollView(
      key: const ValueKey('interests-list'),
      physics: const BouncingScrollPhysics(),
      slivers: [
        if (_selectedTags.isNotEmpty) ...[
          const SliverToBoxAdapter(child: SizedBox(height: 24)),
          const SliverToBoxAdapter(child: _SectionLabel('Selected')),
          SliverToBoxAdapter(
            child: _TagWrap(
              tags: _selectedTags.toList()..sort(),
              selectedTags: _selectedTags,
              onTap: _toggleTag,
            ),
          ),
        ],
        SliverToBoxAdapter(
          child: SizedBox(height: _selectedTags.isEmpty ? 24 : 28),
        ),
        SliverToBoxAdapter(
          child: _SectionLabel(
            _searchController.text.trim().isEmpty ? 'Recommended' : 'Matches',
          ),
        ),
        SliverToBoxAdapter(
          child: _TagWrap(
            tags: _filteredTags,
            selectedTags: _selectedTags,
            onTap: _toggleTag,
          ),
        ),
        const SliverToBoxAdapter(child: SizedBox(height: 24)),
      ],
    );
  }
}

class _Header extends StatelessWidget {
  final int selectedCount;

  const _Header({required this.selectedCount});

  @override
  Widget build(BuildContext context) {
    final remaining = (3 - selectedCount).clamp(0, 3);
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Tune your feed',
            style: TextStyle(
              color: AppTheme.ink,
              fontSize: 32,
              fontWeight: FontWeight.w700,
              height: 1.04,
            ),
          ),
          const SizedBox(height: 10),
          Text(
            remaining == 0
                ? '$selectedCount interests selected'
                : 'Pick $remaining more to continue',
            style: TextStyle(
              color: AppTheme.ink.withValues(alpha: 0.56),
              fontSize: 15,
              height: 1.35,
            ),
          ),
        ],
      ),
    );
  }
}

class _SearchField extends StatelessWidget {
  final TextEditingController controller;

  const _SearchField({required this.controller});

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 52,
      decoration: BoxDecoration(
        color: AppTheme.surface.withValues(alpha: 0.86),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.ink.withValues(alpha: 0.08)),
      ),
      child: CupertinoSearchTextField(
        controller: controller,
        backgroundColor: Colors.transparent,
        borderRadius: BorderRadius.circular(16),
        itemColor: AppTheme.ink.withValues(alpha: 0.58),
        style: const TextStyle(color: AppTheme.ink, fontSize: 15),
        placeholder: 'Search interests',
        placeholderStyle: TextStyle(
          color: AppTheme.ink.withValues(alpha: 0.42),
          fontSize: 15,
        ),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
      ),
    );
  }
}

class _TagWrap extends StatelessWidget {
  final List<String> tags;
  final Set<String> selectedTags;
  final ValueChanged<String> onTap;

  const _TagWrap({
    required this.tags,
    required this.selectedTags,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 0),
      child: Wrap(
        spacing: 9,
        runSpacing: 10,
        children: [
          for (final tag in tags)
            _InterestPill(
              tag: tag,
              isSelected: selectedTags.contains(tag),
              onTap: () => onTap(tag),
            ),
        ],
      ),
    );
  }
}

class _InterestPill extends StatelessWidget {
  final String tag;
  final bool isSelected;
  final VoidCallback onTap;

  const _InterestPill({
    required this.tag,
    required this.isSelected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 160),
        padding: const EdgeInsets.symmetric(horizontal: 15, vertical: 10),
        decoration: BoxDecoration(
          color: isSelected
              ? AppTheme.primary
              : AppTheme.surface.withValues(alpha: 0.82),
          borderRadius: BorderRadius.circular(999),
          border: Border.all(
            color: isSelected
                ? AppTheme.primary
                : AppTheme.ink.withValues(alpha: 0.1),
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (isSelected) ...[
              const Icon(CupertinoIcons.check_mark, size: 14),
              const SizedBox(width: 6),
            ],
            Text(
              tag,
              style: TextStyle(
                color: AppTheme.ink.withValues(alpha: isSelected ? 1 : 0.82),
                fontSize: 14,
                fontWeight: isSelected ? FontWeight.w600 : FontWeight.w500,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _BottomAction extends StatelessWidget {
  final int selectedCount;
  final bool isSaving;
  final VoidCallback onSubmit;

  const _BottomAction({
    required this.selectedCount,
    required this.isSaving,
    required this.onSubmit,
  });

  @override
  Widget build(BuildContext context) {
    final canContinue = selectedCount >= 3 && !isSaving;
    final missing = (3 - selectedCount).clamp(0, 3);

    return DecoratedBox(
      decoration: BoxDecoration(
        color: AppTheme.appBackground.withValues(alpha: 0.94),
        border: Border(
          top: BorderSide(color: AppTheme.ink.withValues(alpha: 0.06)),
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 14, 20, 18),
        child: GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTap: canContinue ? onSubmit : null,
          child: AnimatedOpacity(
            duration: const Duration(milliseconds: 150),
            opacity: selectedCount >= 3 ? 1 : 0.48,
            child: Container(
              height: 54,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: selectedCount >= 3
                    ? AppTheme.primary
                    : AppTheme.surfaceAlt,
                borderRadius: BorderRadius.circular(16),
              ),
              child: isSaving
                  ? const CupertinoActivityIndicator(color: Colors.white)
                  : Text(
                      selectedCount >= 3 ? 'Continue' : 'Select $missing more',
                      style: const TextStyle(
                        color: AppTheme.ink,
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
            ),
          ),
        ),
      ),
    );
  }
}

class _SectionLabel extends StatelessWidget {
  final String text;

  const _SectionLabel(this.text);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Text(
        text,
        style: TextStyle(
          color: AppTheme.ink.withValues(alpha: 0.62),
          fontSize: 13,
          fontWeight: FontWeight.w500,
        ),
      ),
    );
  }
}

class _SubtleNotice extends StatelessWidget {
  final String text;

  const _SubtleNotice({required this.text});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: AppTheme.surface.withValues(alpha: 0.72),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.ink.withValues(alpha: 0.08)),
      ),
      child: Row(
        children: [
          Icon(
            PhosphorIcons.info(PhosphorIconsStyle.regular),
            color: AppTheme.ink.withValues(alpha: 0.58),
            size: 17,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              text,
              style: TextStyle(
                color: AppTheme.ink.withValues(alpha: 0.58),
                fontSize: 12,
                height: 1.3,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _LoadingInterests extends StatelessWidget {
  const _LoadingInterests();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const CupertinoActivityIndicator(color: AppTheme.primary),
          const SizedBox(height: 14),
          Text(
            'Loading interests',
            style: TextStyle(
              color: AppTheme.ink.withValues(alpha: 0.52),
              fontSize: 14,
            ),
          ),
        ],
      ),
    );
  }
}

class _EmptyInterests extends StatelessWidget {
  final String query;
  final VoidCallback onClear;

  const _EmptyInterests({required this.query, required this.onClear});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              PhosphorIcons.magnifyingGlass(PhosphorIconsStyle.light),
              color: AppTheme.ink.withValues(alpha: 0.36),
              size: 34,
            ),
            const SizedBox(height: 12),
            Text(
              'No matches for "$query"',
              textAlign: TextAlign.center,
              style: TextStyle(
                color: AppTheme.ink.withValues(alpha: 0.72),
                fontSize: 15,
                fontWeight: FontWeight.w500,
              ),
            ),
            const SizedBox(height: 10),
            GestureDetector(
              onTap: onClear,
              child: const Text(
                'Clear search',
                style: TextStyle(
                  color: AppTheme.primary,
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
