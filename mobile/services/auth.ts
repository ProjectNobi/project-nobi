/**
 * User authentication service for Nori.
 * Manages user identity, onboarding state, and session.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Crypto from 'expo-crypto';

// ─── Types ───────────────────────────────────────────────────────────────────

export interface UserProfile {
  id: string;
  name: string;
  createdAt: string;
  preferences: UserPreferences;
}

export interface UserPreferences {
  encryptionEnabled: boolean;
  autoDeleteDays: number | null; // null = never
  network: 'mainnet' | 'testnet';
  voiceEnabled: boolean;
  language: string;
}

// ─── Constants ───────────────────────────────────────────────────────────────

const STORAGE_KEYS = {
  USER_PROFILE: '@nobi/user_profile',
  ONBOARDING_COMPLETE: '@nobi/onboarding_complete',
} as const;

const DEFAULT_PREFERENCES: UserPreferences = {
  encryptionEnabled: true,
  autoDeleteDays: null,
  network: 'mainnet',
  voiceEnabled: true,
  language: 'en',
};

// ─── Auth Service ────────────────────────────────────────────────────────────

class AuthService {
  private currentUser: UserProfile | null = null;

  /**
   * Initialize — load existing user or return null.
   */
  async init(): Promise<UserProfile | null> {
    try {
      const raw = await AsyncStorage.getItem(STORAGE_KEYS.USER_PROFILE);
      if (raw) {
        this.currentUser = JSON.parse(raw);
        return this.currentUser;
      }
      return null;
    } catch {
      return null;
    }
  }

  /**
   * Create a new user during onboarding.
   */
  async createUser(name: string): Promise<UserProfile> {
    const id = await this.generateUserId();
    const profile: UserProfile = {
      id,
      name,
      createdAt: new Date().toISOString(),
      preferences: { ...DEFAULT_PREFERENCES },
    };

    await AsyncStorage.setItem(STORAGE_KEYS.USER_PROFILE, JSON.stringify(profile));
    await AsyncStorage.setItem(STORAGE_KEYS.ONBOARDING_COMPLETE, 'true');
    this.currentUser = profile;
    return profile;
  }

  /**
   * Get the current user profile.
   */
  getUser(): UserProfile | null {
    return this.currentUser;
  }

  /**
   * Update user profile.
   */
  async updateUser(updates: Partial<Pick<UserProfile, 'name' | 'preferences'>>): Promise<UserProfile | null> {
    if (!this.currentUser) return null;

    if (updates.name) {
      this.currentUser.name = updates.name;
    }
    if (updates.preferences) {
      this.currentUser.preferences = { ...this.currentUser.preferences, ...updates.preferences };
    }

    await AsyncStorage.setItem(STORAGE_KEYS.USER_PROFILE, JSON.stringify(this.currentUser));
    return this.currentUser;
  }

  /**
   * Check if onboarding has been completed.
   */
  async isOnboarded(): Promise<boolean> {
    const val = await AsyncStorage.getItem(STORAGE_KEYS.ONBOARDING_COMPLETE);
    return val === 'true';
  }

  /**
   * Delete account and all data.
   */
  async deleteAccount(): Promise<void> {
    this.currentUser = null;
    await AsyncStorage.multiRemove([
      STORAGE_KEYS.USER_PROFILE,
      STORAGE_KEYS.ONBOARDING_COMPLETE,
    ]);
    // Note: caller should also clear memories, encryption keys, etc.
  }

  /**
   * Generate a unique anonymous user ID.
   */
  private async generateUserId(): Promise<string> {
    const randomBytes = await Crypto.getRandomBytes(16);
    const hex = Array.from(randomBytes)
      .map((b) => b.toString(16).padStart(2, '0'))
      .join('');
    return `nori_${hex}`;
  }
}

export const auth = new AuthService();
