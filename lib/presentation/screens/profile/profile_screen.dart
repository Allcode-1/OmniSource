import 'package:dio/dio.dart';
import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../core/theme/app_theme.dart';
import '../../../domain/entities/user.dart';
import '../../../domain/repositories/user_repository.dart';
import '../../../presentation/bloc/auth/auth_cubit.dart';
import '../../widgets/user_avatar.dart';
import '../auth/forgot_password_screen.dart';
import '../settings/settings_screen.dart';

class ProfileScreen extends StatefulWidget {
  final UserRepository userRepository;

  const ProfileScreen({super.key, required this.userRepository});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  static const _pagePadding = EdgeInsets.fromLTRB(20, 10, 20, 34);

  User? _user;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _fetchUserData();
  }

  Future<void> _fetchUserData() async {
    User? loadedUser;
    try {
      loadedUser = await widget.userRepository.getMe();
    } catch (_) {
      _showError('Failed to load profile');
    }

    if (!mounted) return;
    setState(() {
      _user = loadedUser;
      _isLoading = false;
    });
  }

  void _showError(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Scaffold(
        backgroundColor: AppTheme.appBackground,
        body: Center(child: CircularProgressIndicator(color: AppTheme.primary)),
      );
    }

    if (_user == null) {
      return Scaffold(
        backgroundColor: AppTheme.appBackground,
        body: SafeArea(
          child: Center(
            child: OutlinedButton(
              onPressed: () {
                setState(() => _isLoading = true);
                _fetchUserData();
              },
              child: const Text('Retry loading profile'),
            ),
          ),
        ),
      );
    }

    return Scaffold(
      backgroundColor: AppTheme.appBackground,
      body: SafeArea(
        child: SingleChildScrollView(
          physics: const BouncingScrollPhysics(),
          padding: _pagePadding,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _buildTopBar(),
              const SizedBox(height: 28),
              _buildAccountCard(),
              const SizedBox(height: 28),
              _buildSetupBlock(),
              if (_user!.interests.isNotEmpty) ...[
                const SizedBox(height: 28),
                _buildInterestsBlock(),
              ],
              const SizedBox(height: 28),
              _buildActionGroup([
                _ProfileAction(
                  title: 'Edit Profile',
                  icon: CupertinoIcons.pencil,
                  onTap: _showEditProfileSheet,
                ),
                _ProfileAction(
                  title: 'Reset Password',
                  icon: CupertinoIcons.lock,
                  onTap: () => Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => const ForgotPasswordScreen(),
                    ),
                  ),
                ),
                _ProfileAction(
                  title: 'Settings',
                  icon: CupertinoIcons.slider_horizontal_3,
                  onTap: () => Navigator.push(
                    context,
                    CupertinoPageRoute(builder: (_) => const SettingsScreen()),
                  ),
                ),
              ]),
              const SizedBox(height: 18),
              _buildActionGroup([
                _ProfileAction(
                  title: 'Logout',
                  icon: CupertinoIcons.square_arrow_right,
                  onTap: _handleLogoutRequest,
                ),
                _ProfileAction(
                  title: 'Delete Account',
                  icon: CupertinoIcons.delete,
                  isDanger: true,
                  onTap: _handleDeleteAccount,
                ),
              ]),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildTopBar() {
    return Stack(
      alignment: Alignment.center,
      children: [
        Align(
          alignment: Alignment.centerLeft,
          child: _CircleButton(
            icon: CupertinoIcons.xmark,
            onTap: () => Navigator.maybePop(context),
          ),
        ),
        const Text(
          'Account',
          style: TextStyle(
            color: AppTheme.ink,
            fontSize: 17,
            fontWeight: FontWeight.w700,
          ),
        ),
      ],
    );
  }

  Widget _buildAccountCard() {
    return Container(
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
      decoration: BoxDecoration(
        color: AppTheme.surfaceAlt,
        borderRadius: BorderRadius.circular(26),
      ),
      child: Row(
        children: [
          UserAvatar(username: _user!.username, size: 58),
          const SizedBox(width: 14),
          Expanded(
            child: Text(
              _user!.username,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: AppTheme.ink,
                fontSize: 19,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
          const SizedBox(width: 10),
          GestureDetector(
            behavior: HitTestBehavior.opaque,
            onTap: _showEditProfileSheet,
            child: const Padding(
              padding: EdgeInsets.symmetric(vertical: 8),
              child: Text(
                'Edit',
                style: TextStyle(
                  color: AppTheme.primary,
                  fontSize: 17,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSetupBlock() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _SoftButton(label: 'Set up Profile', onTap: _showEditProfileSheet),
        const SizedBox(height: 14),
        Text(
          'Set up your profile to keep recommendations personal and make your library feel like yours.',
          style: TextStyle(
            color: AppTheme.ink.withValues(alpha: 0.58),
            fontSize: 15,
            height: 1.35,
          ),
        ),
      ],
    );
  }

  Widget _buildInterestsBlock() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Interests',
          style: TextStyle(
            color: AppTheme.ink.withValues(alpha: 0.55),
            fontSize: 13,
            fontWeight: FontWeight.w600,
          ),
        ),
        const SizedBox(height: 10),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: _user!.interests.map(_buildInterestTag).toList(),
        ),
      ],
    );
  }

  Widget _buildInterestTag(String tag) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: AppTheme.ink.withValues(alpha: 0.08)),
      ),
      child: Text(
        tag,
        style: TextStyle(
          fontSize: 13,
          fontWeight: FontWeight.w500,
          color: AppTheme.ink.withValues(alpha: 0.84),
        ),
      ),
    );
  }

  Widget _buildActionGroup(List<_ProfileAction> actions) {
    return Container(
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        color: AppTheme.surfaceAlt,
        borderRadius: BorderRadius.circular(24),
      ),
      child: Column(
        children: [
          for (var index = 0; index < actions.length; index++) ...[
            _buildActionRow(actions[index]),
            if (index != actions.length - 1)
              Divider(
                height: 1,
                indent: 56,
                color: AppTheme.ink.withValues(alpha: 0.1),
              ),
          ],
        ],
      ),
    );
  }

  Widget _buildActionRow(_ProfileAction action) {
    final color = action.isDanger ? const Color(0xFFFF453A) : AppTheme.primary;
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: action.onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
        child: Row(
          children: [
            Icon(action.icon, color: color, size: 22),
            const SizedBox(width: 16),
            Expanded(
              child: Text(
                action.title,
                style: TextStyle(
                  color: action.isDanger ? color : AppTheme.ink,
                  fontSize: 17,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
            Icon(
              CupertinoIcons.chevron_right,
              color: AppTheme.ink.withValues(alpha: 0.28),
              size: 18,
            ),
          ],
        ),
      ),
    );
  }

  void _showEditProfileSheet() {
    final nameController = TextEditingController(text: _user?.username);
    final tempInterests = List<String>.from(_user?.interests ?? []);

    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (sheetContext) => StatefulBuilder(
        builder: (sheetContext, setModalState) => Padding(
          padding: EdgeInsets.only(
            left: 10,
            right: 10,
            bottom: MediaQuery.of(sheetContext).viewInsets.bottom + 10,
          ),
          child: SafeArea(
            top: false,
            child: Container(
              padding: const EdgeInsets.fromLTRB(20, 18, 20, 18),
              decoration: BoxDecoration(
                color: AppTheme.surface,
                borderRadius: BorderRadius.circular(28),
                border: Border.all(color: AppTheme.ink.withValues(alpha: 0.08)),
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Edit Profile',
                    style: TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.w700,
                      color: AppTheme.ink,
                    ),
                  ),
                  const SizedBox(height: 18),
                  TextField(
                    controller: nameController,
                    style: const TextStyle(color: AppTheme.ink),
                    decoration: const InputDecoration(labelText: 'Username'),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    'Interests',
                    style: TextStyle(
                      fontSize: 13,
                      color: AppTheme.ink.withValues(alpha: 0.64),
                    ),
                  ),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: tempInterests
                        .map(
                          (tag) => Chip(
                            label: Text(
                              tag,
                              style: const TextStyle(fontSize: 12),
                            ),
                            onDeleted: () => setModalState(() {
                              tempInterests.remove(tag);
                            }),
                          ),
                        )
                        .toList(),
                  ),
                  TextButton.icon(
                    onPressed: () async {
                      final newTag = await _showAddTagDialog();
                      if (newTag == null || newTag.trim().isEmpty) return;
                      setModalState(() {
                        tempInterests.add(newTag.trim());
                      });
                    },
                    icon: const Icon(Icons.add, size: 18),
                    label: const Text('Add Interest'),
                  ),
                  const SizedBox(height: 12),
                  SizedBox(
                    width: double.infinity,
                    height: 50,
                    child: ElevatedButton(
                      onPressed: () async {
                        final trimmedName = nameController.text.trim();
                        if (trimmedName.isEmpty) {
                          _showError('Username cannot be empty');
                          return;
                        }
                        try {
                          final navigator = Navigator.of(sheetContext);
                          final updated = await widget.userRepository
                              .updateProfile(
                                username: trimmedName,
                                interests: tempInterests,
                              );
                          if (!mounted || !sheetContext.mounted) return;
                          setState(() => _user = updated);
                          navigator.pop();
                        } catch (e) {
                          var message = 'Failed to update profile';
                          if (e is DioException) {
                            final body = e.response?.data;
                            if (body is Map && body['detail'] is String) {
                              message = body['detail'] as String;
                            }
                          }
                          _showError(message);
                        }
                      },
                      child: const Text('Save Changes'),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Future<String?> _showAddTagDialog() {
    final controller = TextEditingController();
    return showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AppTheme.surface,
        title: const Text(
          'New Interest',
          style: TextStyle(color: AppTheme.ink),
        ),
        content: TextField(
          controller: controller,
          autofocus: true,
          style: const TextStyle(color: AppTheme.ink),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, controller.text),
            child: const Text('Add'),
          ),
        ],
      ),
    );
  }

  Future<void> _handleLogoutRequest() async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AppTheme.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
        title: const Text('Logout', style: TextStyle(color: AppTheme.ink)),
        content: Text(
          'Are you sure you want to exit?',
          style: TextStyle(color: AppTheme.ink.withValues(alpha: 0.78)),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text(
              'Logout',
              style: TextStyle(color: Color(0xFFFF453A)),
            ),
          ),
        ],
      ),
    );

    if (confirm == true && mounted) {
      await context.read<AuthCubit>().logout();
      if (!mounted) return;
      Navigator.of(context).popUntil((route) => route.isFirst);
    }
  }

  Future<void> _handleDeleteAccount() async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AppTheme.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
        title: const Text(
          'Delete Account?',
          style: TextStyle(color: AppTheme.ink),
        ),
        content: Text(
          'This action is permanent.',
          style: TextStyle(color: AppTheme.ink.withValues(alpha: 0.78)),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text(
              'Delete',
              style: TextStyle(color: Color(0xFFFF453A)),
            ),
          ),
        ],
      ),
    );

    if (confirm == true) {
      try {
        await widget.userRepository.deleteAccount();
        if (mounted) {
          await context.read<AuthCubit>().logout();
          if (!mounted) return;
          Navigator.of(context).popUntil((route) => route.isFirst);
        }
      } catch (_) {
        _showError('Failed to delete account');
      }
    }
  }
}

class _CircleButton extends StatelessWidget {
  final IconData icon;
  final VoidCallback onTap;

  const _CircleButton({required this.icon, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: Container(
        width: 54,
        height: 54,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: AppTheme.surface,
          shape: BoxShape.circle,
          border: Border.all(color: AppTheme.ink.withValues(alpha: 0.08)),
        ),
        child: Icon(icon, color: AppTheme.ink, size: 29),
      ),
    );
  }
}

class _SoftButton extends StatelessWidget {
  final String label;
  final VoidCallback onTap;

  const _SoftButton({required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: Container(
        height: 58,
        alignment: Alignment.centerLeft,
        padding: const EdgeInsets.symmetric(horizontal: 22),
        decoration: BoxDecoration(
          color: AppTheme.surfaceAlt,
          borderRadius: BorderRadius.circular(24),
        ),
        child: Text(
          label,
          style: const TextStyle(
            color: AppTheme.primary,
            fontSize: 18,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
    );
  }
}

class _ProfileAction {
  final String title;
  final IconData icon;
  final VoidCallback onTap;
  final bool isDanger;

  const _ProfileAction({
    required this.title,
    required this.icon,
    required this.onTap,
    this.isDanger = false,
  });
}
