/**
 * Settings screen — user profile, privacy controls, network, and account management.
 */

import React, { useState, useCallback, useEffect } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  Pressable,
  Switch,
  TextInput,
  Alert,
} from 'react-native';
import { useRouter } from 'expo-router';
import { theme } from '../../styles/theme';
import { auth, type UserPreferences } from '../../services/auth';
import { encryption } from '../../services/encryption';
import { api } from '../../services/api';
import { memoryStore } from '../../services/memory';

// ─── Section Component ───────────────────────────────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>{title}</Text>
      <View style={styles.sectionContent}>{children}</View>
    </View>
  );
}

function SettingRow({
  label,
  value,
  onPress,
  rightElement,
  destructive = false,
}: {
  label: string;
  value?: string;
  onPress?: () => void;
  rightElement?: React.ReactNode;
  destructive?: boolean;
}) {
  return (
    <Pressable style={styles.settingRow} onPress={onPress} disabled={!onPress && !rightElement}>
      <Text style={[styles.settingLabel, destructive && styles.destructiveLabel]}>{label}</Text>
      {rightElement ?? (value ? <Text style={styles.settingValue}>{value}</Text> : null)}
    </Pressable>
  );
}

// ─── Screen ──────────────────────────────────────────────────────────────────

export default function SettingsScreen() {
  const router = useRouter();
  const user = auth.getUser();
  const [name, setName] = useState(user?.name ?? '');
  const [prefs, setPrefs] = useState<UserPreferences>(
    user?.preferences ?? {
      encryptionEnabled: true,
      autoDeleteDays: null,
      network: 'mainnet',
      voiceEnabled: true,
      language: 'en',
    },
  );
  const [isEditing, setIsEditing] = useState(false);

  // ─── Save name ─────────────────────────────────────────────────────────

  const handleSaveName = useCallback(async () => {
    if (name.trim()) {
      await auth.updateUser({ name: name.trim() });
      setIsEditing(false);
    }
  }, [name]);

  // ─── Toggle preference ─────────────────────────────────────────────────

  const updatePref = useCallback(
    async (key: keyof UserPreferences, value: UserPreferences[keyof UserPreferences]) => {
      const updated = { ...prefs, [key]: value };
      setPrefs(updated);
      await auth.updateUser({ preferences: updated });

      // Side effects
      if (key === 'encryptionEnabled') {
        encryption.setEnabled(value as boolean);
      }
      if (key === 'network') {
        await api.setNetwork(value as 'mainnet' | 'testnet');
      }
    },
    [prefs],
  );

  // ─── Auto-delete options ───────────────────────────────────────────────

  const handleAutoDelete = useCallback(() => {
    Alert.alert('Auto-delete memories', 'Delete memories older than:', [
      { text: 'Never', onPress: () => updatePref('autoDeleteDays', null) },
      { text: '7 days', onPress: () => updatePref('autoDeleteDays', 7) },
      { text: '30 days', onPress: () => updatePref('autoDeleteDays', 30) },
      { text: '90 days', onPress: () => updatePref('autoDeleteDays', 90) },
      { text: 'Cancel', style: 'cancel' },
    ]);
  }, [updatePref]);

  // ─── Export data ───────────────────────────────────────────────────────

  const handleExport = useCallback(async () => {
    if (!user) return;
    const json = await memoryStore.exportAsJson(user.id);
    Alert.alert('Data Exported', `${json.length} characters of data ready to share.`);
  }, [user]);

  // ─── Delete account ────────────────────────────────────────────────────

  const handleDeleteAccount = useCallback(() => {
    Alert.alert(
      '⚠️ Delete Account',
      'This will permanently delete your profile, all memories, and encryption keys. This cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete Everything',
          style: 'destructive',
          onPress: async () => {
            if (user) {
              await api.deleteAllMemories(user.id);
              await memoryStore.clearLocal(user.id);
              await encryption.deleteKey(user.id);
              await auth.deleteAccount();
              router.replace('/onboarding');
            }
          },
        },
      ],
    );
  }, [user, router]);

  if (!user) {
    return (
      <View style={styles.container}>
        <Text style={styles.errorText}>No user profile found</Text>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.scrollContent}>
      {/* Profile */}
      <Section title="Profile">
        {isEditing ? (
          <View style={styles.editRow}>
            <TextInput
              style={styles.nameInput}
              value={name}
              onChangeText={setName}
              placeholder="Your name"
              placeholderTextColor={theme.colors.textMuted}
              autoFocus
            />
            <Pressable style={styles.saveButton} onPress={handleSaveName}>
              <Text style={styles.saveButtonText}>Save</Text>
            </Pressable>
          </View>
        ) : (
          <SettingRow
            label="Name"
            value={user.name}
            onPress={() => setIsEditing(true)}
          />
        )}
        <SettingRow label="User ID" value={user.id.slice(0, 16) + '...'} />
        <SettingRow label="Member since" value={new Date(user.createdAt).toLocaleDateString()} />
      </Section>

      {/* Privacy */}
      <Section title="Privacy">
        <SettingRow
          label="End-to-end encryption"
          rightElement={
            <Switch
              value={prefs.encryptionEnabled}
              onValueChange={(v) => updatePref('encryptionEnabled', v)}
              trackColor={{ true: theme.colors.primary, false: theme.colors.surface }}
              thumbColor={theme.colors.text}
            />
          }
        />
        <SettingRow
          label="Auto-delete memories"
          value={prefs.autoDeleteDays ? `After ${prefs.autoDeleteDays} days` : 'Never'}
          onPress={handleAutoDelete}
        />
        <SettingRow
          label="Voice features"
          rightElement={
            <Switch
              value={prefs.voiceEnabled}
              onValueChange={(v) => updatePref('voiceEnabled', v)}
              trackColor={{ true: theme.colors.primary, false: theme.colors.surface }}
              thumbColor={theme.colors.text}
            />
          }
        />
      </Section>

      {/* Network */}
      <Section title="Network">
        <SettingRow
          label="Mainnet"
          rightElement={
            <Pressable
              style={[
                styles.networkButton,
                prefs.network === 'mainnet' && styles.networkButtonActive,
              ]}
              onPress={() => updatePref('network', 'mainnet')}
            >
              <Text
                style={[
                  styles.networkButtonText,
                  prefs.network === 'mainnet' && styles.networkButtonTextActive,
                ]}
              >
                {prefs.network === 'mainnet' ? '✓ Active' : 'Select'}
              </Text>
            </Pressable>
          }
        />
        <SettingRow
          label="Testnet"
          rightElement={
            <Pressable
              style={[
                styles.networkButton,
                prefs.network === 'testnet' && styles.networkButtonActive,
              ]}
              onPress={() => updatePref('network', 'testnet')}
            >
              <Text
                style={[
                  styles.networkButtonText,
                  prefs.network === 'testnet' && styles.networkButtonTextActive,
                ]}
              >
                {prefs.network === 'testnet' ? '✓ Active' : 'Select'}
              </Text>
            </Pressable>
          }
        />
      </Section>

      {/* Data */}
      <Section title="Data">
        <SettingRow label="📤 Export all data" onPress={handleExport} />
        <SettingRow label="🗑️ Delete account" onPress={handleDeleteAccount} destructive />
      </Section>

      {/* About */}
      <Section title="About">
        <SettingRow label="Version" value="1.0.0" />
        <SettingRow label="Powered by" value="Project Nobi (Bittensor)" />
      </Section>
    </ScrollView>
  );
}

// ─── Styles ──────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.background,
  },
  scrollContent: {
    paddingBottom: theme.spacing.xl,
  },
  section: {
    paddingTop: theme.spacing.lg,
  },
  sectionTitle: {
    fontSize: theme.fontSize.xs,
    color: theme.colors.textMuted,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 1,
    paddingHorizontal: theme.spacing.md,
    marginBottom: theme.spacing.sm,
  },
  sectionContent: {
    backgroundColor: theme.colors.surface,
    borderTopWidth: 1,
    borderBottomWidth: 1,
    borderColor: theme.colors.border,
  },
  settingRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.border,
    minHeight: 48,
  },
  settingLabel: {
    fontSize: theme.fontSize.md,
    color: theme.colors.text,
    flex: 1,
  },
  destructiveLabel: {
    color: theme.colors.error,
  },
  settingValue: {
    fontSize: theme.fontSize.md,
    color: theme.colors.textSecondary,
  },
  editRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.sm,
    gap: theme.spacing.sm,
  },
  nameInput: {
    flex: 1,
    backgroundColor: theme.colors.background,
    borderRadius: theme.borderRadius.md,
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.sm,
    color: theme.colors.text,
    fontSize: theme.fontSize.md,
    borderWidth: 1,
    borderColor: theme.colors.primary,
  },
  saveButton: {
    backgroundColor: theme.colors.primary,
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.sm,
    borderRadius: theme.borderRadius.md,
  },
  saveButtonText: {
    color: theme.colors.text,
    fontWeight: '600',
  },
  networkButton: {
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.xs,
    borderRadius: theme.borderRadius.pill,
    borderWidth: 1,
    borderColor: theme.colors.border,
  },
  networkButtonActive: {
    backgroundColor: theme.colors.primary,
    borderColor: theme.colors.primary,
  },
  networkButtonText: {
    fontSize: theme.fontSize.sm,
    color: theme.colors.textSecondary,
  },
  networkButtonTextActive: {
    color: theme.colors.text,
    fontWeight: '600',
  },
  errorText: {
    color: theme.colors.error,
    fontSize: theme.fontSize.md,
    textAlign: 'center',
    paddingTop: 100,
  },
});
