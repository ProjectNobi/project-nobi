/**
 * Onboarding screen — 3-step intro: Meet Nori → She Remembers → Your Privacy.
 */

import React, { useState, useCallback, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  TextInput,
  FlatList,
  Dimensions,
  type ViewToken,
} from 'react-native';
import { useRouter } from 'expo-router';
import { theme } from '../styles/theme';
import { auth } from '../services/auth';
import { encryption } from '../services/encryption';
import { NoriAvatar } from '../components/NoriAvatar';

const { width: SCREEN_WIDTH } = Dimensions.get('window');

// ─── Onboarding Steps ────────────────────────────────────────────────────────

interface OnboardingStep {
  id: string;
  emoji: string;
  title: string;
  subtitle: string;
  description: string;
}

const STEPS: OnboardingStep[] = [
  {
    id: 'meet',
    emoji: '🌸',
    title: 'Meet Nori',
    subtitle: 'Your Personal AI Companion',
    description:
      "Nori is your always-available AI friend. She's warm, thoughtful, and genuinely cares about you. Chat about anything — your day, your dreams, your worries.",
  },
  {
    id: 'memory',
    emoji: '🧠',
    title: 'She Remembers',
    subtitle: 'A Companion Who Knows You',
    description:
      "Unlike other AI chatbots, Nori remembers what matters to you. Your name, your preferences, important events. She grows with you and gets better over time.",
  },
  {
    id: 'privacy',
    emoji: '🔒',
    title: 'Your Privacy',
    subtitle: 'End-to-End Encrypted',
    description:
      "Your conversations are encrypted and your data stays yours. You can export or delete everything at any time. Nori runs on Bittensor's decentralized network — no single company owns your data.",
  },
];

// ─── Screen ──────────────────────────────────────────────────────────────────

export default function OnboardingScreen() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(0);
  const [name, setName] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const flatListRef = useRef<FlatList<OnboardingStep>>(null);

  const isLastStep = currentStep === STEPS.length - 1;

  // ─── Navigation ────────────────────────────────────────────────────────

  const goNext = useCallback(() => {
    if (currentStep < STEPS.length - 1) {
      flatListRef.current?.scrollToIndex({ index: currentStep + 1, animated: true });
    }
  }, [currentStep]);

  const handleViewableItemsChanged = useCallback(
    ({ viewableItems }: { viewableItems: ViewToken[] }) => {
      if (viewableItems.length > 0 && viewableItems[0].index != null) {
        setCurrentStep(viewableItems[0].index);
      }
    },
    [],
  );

  // ─── Start chatting ────────────────────────────────────────────────────

  const handleStart = useCallback(async () => {
    const userName = name.trim() || 'Friend';
    setIsCreating(true);

    try {
      const user = await auth.createUser(userName);
      await encryption.init(user.id);
      router.replace('/');
    } catch (err) {
      console.error('Onboarding error:', err);
      setIsCreating(false);
    }
  }, [name, router]);

  // ─── Render step ───────────────────────────────────────────────────────

  const renderStep = useCallback(
    ({ item }: { item: OnboardingStep }) => (
      <View style={styles.stepContainer}>
        <View style={styles.stepContent}>
          {item.id === 'meet' ? (
            <NoriAvatar size={100} isAnimating />
          ) : (
            <Text style={styles.stepEmoji}>{item.emoji}</Text>
          )}
          <Text style={styles.stepTitle}>{item.title}</Text>
          <Text style={styles.stepSubtitle}>{item.subtitle}</Text>
          <Text style={styles.stepDescription}>{item.description}</Text>
        </View>
      </View>
    ),
    [],
  );

  return (
    <View style={styles.container}>
      {/* Steps carousel */}
      <FlatList
        ref={flatListRef}
        data={STEPS}
        renderItem={renderStep}
        keyExtractor={(item) => item.id}
        horizontal
        pagingEnabled
        showsHorizontalScrollIndicator={false}
        onViewableItemsChanged={handleViewableItemsChanged}
        viewabilityConfig={{ viewAreaCoveragePercentThreshold: 50 }}
        scrollEnabled
      />

      {/* Dots indicator */}
      <View style={styles.dotsContainer}>
        {STEPS.map((_, i) => (
          <View
            key={`dot-${i}`}
            style={[styles.dot, i === currentStep && styles.dotActive]}
          />
        ))}
      </View>

      {/* Bottom area */}
      <View style={styles.bottomContainer}>
        {isLastStep ? (
          <>
            {/* Name input */}
            <Text style={styles.nameLabel}>What should Nori call you?</Text>
            <TextInput
              style={styles.nameInput}
              value={name}
              onChangeText={setName}
              placeholder="Your name"
              placeholderTextColor={theme.colors.textMuted}
              autoCapitalize="words"
              maxLength={50}
            />

            {/* Start button */}
            <Pressable
              style={[styles.startButton, isCreating && styles.buttonDisabled]}
              onPress={handleStart}
              disabled={isCreating}
            >
              <Text style={styles.startButtonText}>
                {isCreating ? 'Setting up...' : '✨ Start Chatting'}
              </Text>
            </Pressable>
          </>
        ) : (
          <Pressable style={styles.nextButton} onPress={goNext}>
            <Text style={styles.nextButtonText}>Next →</Text>
          </Pressable>
        )}

        {/* Skip */}
        {!isLastStep && (
          <Pressable
            style={styles.skipButton}
            onPress={() =>
              flatListRef.current?.scrollToIndex({ index: STEPS.length - 1, animated: true })
            }
          >
            <Text style={styles.skipButtonText}>Skip</Text>
          </Pressable>
        )}
      </View>
    </View>
  );
}

// ─── Styles ──────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.background,
  },
  stepContainer: {
    width: SCREEN_WIDTH,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: theme.spacing.xl,
  },
  stepContent: {
    alignItems: 'center',
    paddingTop: 80,
  },
  stepEmoji: {
    fontSize: 80,
    marginBottom: theme.spacing.lg,
  },
  stepTitle: {
    fontSize: theme.fontSize.xxl,
    fontWeight: '700',
    color: theme.colors.text,
    marginTop: theme.spacing.lg,
    textAlign: 'center',
  },
  stepSubtitle: {
    fontSize: theme.fontSize.lg,
    color: theme.colors.primaryLight,
    marginTop: theme.spacing.sm,
    textAlign: 'center',
  },
  stepDescription: {
    fontSize: theme.fontSize.md,
    color: theme.colors.textSecondary,
    textAlign: 'center',
    marginTop: theme.spacing.lg,
    lineHeight: 24,
    maxWidth: 320,
  },
  dotsContainer: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: theme.spacing.sm,
    paddingVertical: theme.spacing.md,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: theme.colors.textMuted,
  },
  dotActive: {
    backgroundColor: theme.colors.primary,
    width: 24,
  },
  bottomContainer: {
    paddingHorizontal: theme.spacing.xl,
    paddingBottom: 60,
    alignItems: 'center',
    gap: theme.spacing.md,
  },
  nameLabel: {
    fontSize: theme.fontSize.md,
    color: theme.colors.textSecondary,
    marginBottom: theme.spacing.xs,
  },
  nameInput: {
    width: '100%',
    backgroundColor: theme.colors.surface,
    borderRadius: theme.borderRadius.lg,
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.md,
    color: theme.colors.text,
    fontSize: theme.fontSize.lg,
    textAlign: 'center',
    borderWidth: 1,
    borderColor: theme.colors.border,
  },
  startButton: {
    width: '100%',
    backgroundColor: theme.colors.primary,
    paddingVertical: theme.spacing.md,
    borderRadius: theme.borderRadius.lg,
    alignItems: 'center',
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  startButtonText: {
    color: theme.colors.text,
    fontSize: theme.fontSize.lg,
    fontWeight: '700',
  },
  nextButton: {
    width: '100%',
    backgroundColor: theme.colors.primary,
    paddingVertical: theme.spacing.md,
    borderRadius: theme.borderRadius.lg,
    alignItems: 'center',
  },
  nextButtonText: {
    color: theme.colors.text,
    fontSize: theme.fontSize.lg,
    fontWeight: '600',
  },
  skipButton: {
    paddingVertical: theme.spacing.sm,
  },
  skipButtonText: {
    color: theme.colors.textMuted,
    fontSize: theme.fontSize.md,
  },
});
