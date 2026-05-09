export type SessionStatus = 'idle' | 'presenting' | 'paused' | 'answering' | 'ended';

export interface DeckManifestSlide {
  index: number;
  title: string;
  summary: string;
  image_url: string | null;
  top_terms?: string[];
}

export interface DeckManifest {
  deck_id: string;
  title: string;
  slide_count: number;
  slides: DeckManifestSlide[];
}

export interface DeckSummary {
  id: string;
  title: string;
  pdf_path: string;
  status: string;
  slide_count: number;
  manifest_json?: DeckManifest | Record<string, unknown> | string;
  created_at: string;
  updated_at: string;
}

export interface Slide {
  id: string;
  deck_id: string;
  index: number;
  title: string;
  image_url: string | null;
  raw_text: string;
  speaker_notes: string | null;
  summary: string;
  talk_track: string;
  faq_json: string[];
}

export interface TranscriptEvent {
  id: string;
  session_id: string;
  role: 'user' | 'agent' | 'system';
  text: string;
  created_at: string;
}

export interface PresentationSession {
  id: string;
  deck_id: string;
  public_token: string;
  status: SessionStatus;
  current_slide_index: number;
  started_at: string | null;
  autoplay_enabled: boolean;
  autoplay_interval_seconds: number;
  autoplay_started_at: string | null;
  updated_at: string;
}

export interface AvatarSession {
  provider: string;
  enabled: boolean;
  session_id: string;
  avatar_id: string | null;
  voice_id: string | null;
  public_token: string;
  status: string;
  note?: string | null;
  stream_url?: string | null;
  access_token?: string | null;
  ice_servers?: Array<Record<string, unknown>> | null;
  live_session?: Record<string, unknown> | null;
}

export interface PipecatToolContract {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  endpoint?: string;
  method?: string;
}

export interface RealtimeClientConfig {
  provider: string;
  enabled: boolean;
  session_id: string;
  public_token: string;
  realtime_service_url: string;
  pipecat_service_url?: string;
  model: string;
  status: string;
  bridge_configured?: boolean;
  browser_direct_supported?: boolean;
  client_secret?: string | null;
  instructions?: string | null;
  current_slide_index?: number | null;
  live_session?: Record<string, unknown> | null;
  next_step?: string | null;
  tool_manifest?: PipecatToolContract[] | null;
  pipecat_plan?: Record<string, unknown> | null;
}

export interface SessionSnapshot {
  session: PresentationSession;
  deck: DeckSummary;
  slides: Slide[];
  transcript: TranscriptEvent[];
  avatar: AvatarSession | null;
  realtime: RealtimeClientConfig | null;
}

export interface SessionLiveState {
  session: PresentationSession;
  current_slide: Slide | null;
  transcript: TranscriptEvent[];
  recent_events: Array<{
    id: string;
    session_id: string;
    type: string;
    payload_json: string;
    created_at: string;
  }>;
  upcoming_slides: Slide[];
  progress: {
    current_slide_number: number;
    slide_count: number;
    remaining_slides: number;
    has_started: boolean;
  };
}

export interface PipecatLiveSession {
  session_id: string;
  public_token?: string | null;
  state: string;
  transport_ready: boolean;
  openai_ready: boolean;
  video_ready: boolean;
  last_error?: string | null;
  events?: Array<Record<string, unknown>>;
  created_at?: string;
  updated_at?: string;
}

export interface PipecatAgentStatus {
  status: string;
  sessionId: string;
  publicToken?: string | null;
  connected: boolean;
  agent_status?: string;
  transport_mode?: string;
  instructions?: string | null;
  tool_manifest?: PipecatToolContract[] | null;
  avatar?: AvatarSession | Record<string, unknown> | null;
  realtime?: RealtimeClientConfig | Record<string, unknown> | null;
  live_session?: PipecatLiveSession | Record<string, unknown> | null;
  tool_state?: Record<string, unknown> | null;
  nextStep?: string | null;
}

export interface PipecatLiveCreateResponse {
  status: string;
  sessionId: string;
  publicToken?: string | null;
  live: PipecatLiveSession;
  agent?: PipecatAgentStatus | null;
  transport?: {
    provider?: string;
    join_url?: string;
    ice_url?: string;
    state_url?: string;
    stop_url?: string;
  } | null;
  providers?: Record<string, unknown> | null;
  nextStep?: string | null;
}

export interface VoicePipelineStatus {
  status: string;
  mode?: string | null;
  start_endpoint?: string | null;
  ask_endpoint?: string | null;
  stop_endpoint?: string | null;
  transcript?: string | null;
  answer?: string | null;
  instructions?: string | null;
  agent?: PipecatAgentStatus | null;
  transport?: {
    provider?: string;
    configured?: boolean;
    connect_url?: string | null;
    client_secret?: string | null;
    live_session?: Record<string, unknown> | PipecatLiveSession | null;
    instructions?: string | null;
    model?: string | null;
    [key: string]: unknown;
  } | null;
}

export interface BootstrapStatus {
  status: string;
  reason?: string | null;
  nextStep?: string | null;
  avatar_live_ready?: boolean;
  avatar?: AvatarSession | null;
  realtime?: RealtimeClientConfig | null;
  voice?: VoicePipelineStatus | null;
  agent?: PipecatAgentStatus | null;
  pipecatPlan?: Record<string, unknown> | null;
  contract?: Record<string, unknown> | null;
}

export interface AskResponse {
  answer: string;
  citations: Array<{ slide_index: number; reason: string }>;
  session_status: SessionStatus;
}

export interface SessionCreateResponse {
  session_id: string;
  public_token: string;
  public_url: string;
  status: SessionStatus;
  api_base_url?: string;
}

export interface DeckSlidesResponse {
  deck_id: string;
  slides: Array<{
    id: string;
    index: number;
    title: string;
    summary: string;
    image_url: string | null;
  }>;
}

export interface DefaultDeckMeta {
  available: boolean;
  name: string;
}
