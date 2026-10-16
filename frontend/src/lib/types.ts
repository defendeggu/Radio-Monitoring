// Shapes of the API responses used by the UI (see /api/openapi.json for the full API)

export type Modulation = 'FM' | 'AM' | 'USB' | 'LSB';
export type DeviceType = 'auto' | 'hackrf' | 'rtlsdr' | 'airspyhf' | 'usrp';

export interface SdrDetect {
  detected: boolean;
  type: string;
  message?: string;
  frequency_range?: { min_hz: number; max_hz: number; min_mhz: number; max_mhz: number };
  max_sample_rate_hz?: number;
}

export interface LockHolder {
  owner: string;
  kind: string;
  since: string;
  details: Record<string, unknown>;
}

export interface StreamSession {
  session_id: string;
  mode: string;
  frequency: number;
  duration: number;
  gain: number;
  sample_rate: number;
  status: 'starting' | 'running' | 'stopping' | 'completed' | 'failed';
  start_time: string;
  end_time: string | null;
  packet_count: number;
  last_packet_time: string | null;
  error: string | null;
  channel_configs?: { mode: string; frequency: number; label: string }[] | null;
}

export interface SdrStatus {
  busy: boolean;
  holder: LockHolder | null;
  active_sessions: StreamSession[];
}

export interface CaptureJob {
  capture_id: string;
  status: 'queued' | 'capturing' | 'processing' | 'completed' | 'failed';
  mode: string;
  created_at: string;
  result: CaptureResult | null;
  error: string | null;
}

export interface Segment {
  start: number;
  end: number;
  text: string;
}

export interface CaptureResult {
  status: string;
  mode: string;
  capture: { id?: string; audio_file: string; frequency: number; modulation: string; duration: number };
  transcription?: {
    text: string;
    language: string;
    language_probability: number;
    duration: number;
    segments: Segment[];
  };
  aprs?: { packet_count: number; packets: AprsPacket[] };
  pocsag?: { message_count: number; messages: PocsagMessage[] };
  simulation_mode?: boolean;
  warning?: string;
}

export interface AprsPacket {
  uuid?: string;
  source_callsign: string;
  destination_callsign?: string;
  path?: string;
  aprs_type?: string;
  packet_type?: string;
  latitude?: number | null;
  longitude?: number | null;
  altitude?: number | null;
  speed?: number | null;
  course?: number | null;
  message_text?: string | null;
  maidenhead?: string;
  timestamp?: string;
  '@timestamp'?: string;
  frequency?: number;
}

export interface PocsagMessage {
  uuid?: string;
  address: number;
  function_code?: number;
  message_type: string;
  baud_rate: number;
  message_text?: string | null;
  timestamp?: string;
  '@timestamp'?: string;
  frequency?: number;
}

export interface Aircraft {
  icao: string;
  flight?: string | null;
  altitude_ft?: number | null;
  ground_speed_kt?: number | null;
  track?: number | null;
  squawk?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  rssi?: number | null;
  seen?: number;
}

export interface Bookmark {
  id: string;
  name: string;
  frequency: number;
  modulation: Modulation;
  mode: 'voice' | 'aprs' | 'pocsag' | 'vox' | 'adsb' | 'ais' | 'ism';
  notes: string;
  tags: string[];
}

export interface AlertRule {
  id: string;
  name: string;
  enabled: boolean;
  source: string;
  field: string;
  match_type: 'contains' | 'equals' | 'regex';
  pattern: string;
  case_sensitive: boolean;
  channels: string[];
  cooldown_seconds: number;
}

export interface AlertEvent {
  uuid: string;
  timestamp: string;
  rule_id: string;
  rule_name: string;
  source: string;
  summary: string;
}

export interface Schedule {
  id: string;
  name: string;
  enabled: boolean;
  cron: string;
  action: 'stream' | 'capture' | 'vox' | 'decoder';
  params: Record<string, unknown>;
  next_run: string | null;
  last_run?: string;
  last_status?: string;
  last_detail?: Record<string, unknown> | null;
}

export interface Recording {
  filename: string;
  size: number;
  created: string;
  has_transcript: boolean;
}

export interface DashboardStats {
  hours: number;
  counts: Record<string, number>;
  timeline: ({ time: string } & Record<string, number | string>)[];
  latest: { aprs: AprsPacket[]; pocsag: PocsagMessage[]; captures: Record<string, unknown>[] };
}

export interface LiveEvent<T = Record<string, unknown>> {
  type: string;
  time: string;
  data: T;
}
