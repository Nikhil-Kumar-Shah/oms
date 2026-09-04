/**
 * Authentication & Session Types
 */

import { UserProfile } from './user';

export interface UserSession {
  token: string;
  token_type: string;
  expires_at: string;
}

export interface LoginResponse {
  success: boolean;
  session: UserSession;
  user: UserProfile;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}
