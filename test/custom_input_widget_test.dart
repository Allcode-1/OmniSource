import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:omnisource/presentation/widgets/custom_input.dart';

Widget _wrap(Widget child) {
  return MaterialApp(
    home: Scaffold(body: Form(child: child)),
  );
}

void main() {
  group('CustomInput widget', () {
    testWidgets('renders label and hint text', (tester) async {
      final controller = TextEditingController();
      addTearDown(controller.dispose);

      await tester.pumpWidget(
        _wrap(
          CustomInput(
            label: 'Email',
            icon: Icons.email,
            controller: controller,
          ),
        ),
      );

      expect(find.text('Email'), findsOneWidget);
      expect(find.text('Enter your Email'), findsOneWidget);
      expect(find.byIcon(Icons.email), findsOneWidget);
    });

    testWidgets('updates controller value on text entry', (tester) async {
      final controller = TextEditingController();
      addTearDown(controller.dispose);

      await tester.pumpWidget(
        _wrap(CustomInput(label: 'Username', controller: controller)),
      );

      await tester.enterText(find.byType(TextFormField), 'neo');
      expect(controller.text, 'neo');
    });

    testWidgets('applies obscureText for password mode', (tester) async {
      final controller = TextEditingController();
      addTearDown(controller.dispose);

      await tester.pumpWidget(
        _wrap(
          CustomInput(
            label: 'Password',
            isPassword: true,
            controller: controller,
          ),
        ),
      );

      final editableText = tester.widget<EditableText>(
        find.byType(EditableText),
      );
      expect(editableText.obscureText, isTrue);
    });

    testWidgets('validator message is shown after validate', (tester) async {
      final controller = TextEditingController();
      final formKey = GlobalKey<FormState>();
      addTearDown(controller.dispose);

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Form(
              key: formKey,
              child: CustomInput(
                label: 'Email',
                controller: controller,
                validator: (value) =>
                    (value == null || value.isEmpty) ? 'Required' : null,
              ),
            ),
          ),
        ),
      );

      formKey.currentState!.validate();
      await tester.pump();

      expect(find.text('Required'), findsOneWidget);
    });
  });
}
