-- Radio Monitoring Database Schema
-- PostgreSQL initialization script

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For text search

-- Create main captures table
CREATE TABLE IF NOT EXISTS captures (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,

    -- Timestamp
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,

    -- Radio parameters
    frequency BIGINT NOT NULL CHECK (frequency > 0),
    modulation VARCHAR(10) NOT NULL CHECK (modulation IN ('FM', 'AM', 'USB', 'LSB')),
    duration INTEGER NOT NULL CHECK (duration > 0),
    gain INTEGER NOT NULL CHECK (gain >= 0 AND gain <= 47),
    sample_rate INTEGER NOT NULL DEFAULT 2000000,

    -- File information
    audio_file_path VARCHAR(500) NOT NULL,
    json_file_path VARCHAR(500),
    file_size BIGINT,

    -- Transcription results
    transcription_text TEXT,
    language VARCHAR(10),
    language_confidence FLOAT CHECK (language_confidence >= 0 AND language_confidence <= 1),
    transcription_duration FLOAT,

    -- Metadata stored as JSON
    segments JSONB,
    metadata JSONB,

    -- Status tracking
    status VARCHAR(20) DEFAULT 'completed' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    error_message TEXT
);

-- Add mode column for APRS and POCSAG support
ALTER TABLE captures ADD COLUMN IF NOT EXISTS mode VARCHAR(20) DEFAULT 'voice'
    CHECK (mode IN ('voice', 'aprs', 'pocsag'));

-- Create indices for performance
CREATE INDEX IF NOT EXISTS idx_captures_created_at ON captures(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_captures_frequency ON captures(frequency);
CREATE INDEX IF NOT EXISTS idx_captures_modulation ON captures(modulation);
CREATE INDEX IF NOT EXISTS idx_captures_language ON captures(language);
CREATE INDEX IF NOT EXISTS idx_captures_status ON captures(status);
CREATE INDEX IF NOT EXISTS idx_captures_mode ON captures(mode);

-- Full-text search index on transcription
CREATE INDEX IF NOT EXISTS idx_transcription_text_gin ON captures USING gin(to_tsvector('english', COALESCE(transcription_text, '')));

-- Trigram index for partial text search
CREATE INDEX IF NOT EXISTS idx_transcription_text_trgm ON captures USING gin(transcription_text gin_trgm_ops);

-- JSON indices for segments
CREATE INDEX IF NOT EXISTS idx_segments_gin ON captures USING gin(segments);

-- Create APRS messages table
CREATE TABLE IF NOT EXISTS aprs_messages (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,

    -- Link to parent capture
    capture_id INTEGER NOT NULL REFERENCES captures(id) ON DELETE CASCADE,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    decoded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,

    -- Station identification
    source_callsign VARCHAR(20) NOT NULL,
    destination_callsign VARCHAR(20),
    path VARCHAR(200),

    -- Position data (nullable - not all APRS messages have position)
    latitude DECIMAL(10, 7),
    longitude DECIMAL(11, 7),
    altitude_meters INTEGER,

    -- Movement data
    speed_kmh DECIMAL(6, 2),
    course_degrees INTEGER CHECK (course_degrees >= 0 AND course_degrees < 360),

    -- Message content
    message_text TEXT,
    symbol_table CHAR(1),
    symbol_code CHAR(1),

    -- Raw packet data
    raw_packet TEXT NOT NULL,
    aprs_type VARCHAR(50),

    -- Parsed APRS data as JSON for extensibility
    aprs_data JSONB,
    weather_data JSONB,
    telemetry_data JSONB,

    -- Quality metrics
    signal_strength INTEGER,
    decode_confidence FLOAT
);

-- Indices for APRS messages
CREATE INDEX IF NOT EXISTS idx_aprs_capture_id ON aprs_messages(capture_id);
CREATE INDEX IF NOT EXISTS idx_aprs_source_callsign ON aprs_messages(source_callsign);
CREATE INDEX IF NOT EXISTS idx_aprs_created_at ON aprs_messages(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_aprs_type ON aprs_messages(aprs_type);

-- Geospatial index for map queries
CREATE INDEX IF NOT EXISTS idx_aprs_location ON aprs_messages USING GIST (
    POINT(longitude, latitude)
) WHERE latitude IS NOT NULL AND longitude IS NOT NULL;

-- Full-text search on message text
CREATE INDEX IF NOT EXISTS idx_aprs_message_text_gin ON aprs_messages
    USING gin(to_tsvector('english', COALESCE(message_text, '')));

-- JSONB queries
CREATE INDEX IF NOT EXISTS idx_aprs_data_gin ON aprs_messages USING gin(aprs_data);

-- Create POCSAG messages table
CREATE TABLE IF NOT EXISTS pocsag_messages (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,

    -- Link to parent capture
    capture_id INTEGER NOT NULL REFERENCES captures(id) ON DELETE CASCADE,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    decoded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,

    -- POCSAG message data
    address BIGINT NOT NULL CHECK (address >= 0),
    function_code INTEGER NOT NULL CHECK (function_code >= 0 AND function_code <= 3),
    message_type VARCHAR(20) NOT NULL CHECK (message_type IN ('alphanumeric', 'numeric', 'tone')),
    message_text TEXT,
    baud_rate INTEGER NOT NULL CHECK (baud_rate IN (512, 1200, 2400)),

    -- Raw packet data
    raw_packet TEXT NOT NULL,

    -- Extended data as JSON for future extensibility
    pocsag_data JSONB,

    -- Quality metrics
    signal_strength INTEGER,
    decode_confidence FLOAT
);

-- Indices for POCSAG messages
CREATE INDEX IF NOT EXISTS idx_pocsag_capture_id ON pocsag_messages(capture_id);
CREATE INDEX IF NOT EXISTS idx_pocsag_address ON pocsag_messages(address);
CREATE INDEX IF NOT EXISTS idx_pocsag_created_at ON pocsag_messages(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pocsag_message_type ON pocsag_messages(message_type);
CREATE INDEX IF NOT EXISTS idx_pocsag_baud_rate ON pocsag_messages(baud_rate);

-- Full-text search on message text
CREATE INDEX IF NOT EXISTS idx_pocsag_message_text_gin ON pocsag_messages
    USING gin(to_tsvector('english', COALESCE(message_text, '')));

-- JSONB queries
CREATE INDEX IF NOT EXISTS idx_pocsag_data_gin ON pocsag_messages USING gin(pocsag_data);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger to automatically update updated_at
CREATE TRIGGER update_captures_updated_at
    BEFORE UPDATE ON captures
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Create trigger for APRS messages updated_at
CREATE TRIGGER update_aprs_messages_updated_at
    BEFORE UPDATE ON aprs_messages
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Create trigger for POCSAG messages updated_at
CREATE TRIGGER update_pocsag_messages_updated_at
    BEFORE UPDATE ON pocsag_messages
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- REPEATER MONITORING TABLES
-- ============================================================================

-- Table for Swiss amateur radio repeaters
CREATE TABLE IF NOT EXISTS repeaters (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,

    -- Repeater identification
    callsign VARCHAR(20) NOT NULL,
    name VARCHAR(100),

    -- Technical parameters
    output_frequency BIGINT NOT NULL CHECK (output_frequency > 0),  -- Hz
    input_frequency BIGINT NOT NULL CHECK (input_frequency > 0),    -- Hz
    offset_mhz DECIMAL(6,4),           -- e.g., -0.6 for 600kHz shift
    ctcss_tone DECIMAL(5,1),           -- e.g., 123.0 Hz
    modulation VARCHAR(20) DEFAULT 'FM',

    -- Repeater type (for filtering)
    mode VARCHAR(20) NOT NULL CHECK (mode IN ('FM', 'DMR', 'D-STAR', 'Fusion', 'P25', 'C4FM')),
    band VARCHAR(10) CHECK (band IN ('2m', '70cm', '23cm')),

    -- Location data
    latitude DECIMAL(10, 7),
    longitude DECIMAL(11, 7),
    elevation_meters INTEGER,
    canton VARCHAR(2),  -- e.g., 'ZH', 'BE', 'GE'
    location_name VARCHAR(100),

    -- Status
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'testing')),

    -- Metadata
    metadata JSONB
);

-- Indices for repeaters
CREATE INDEX IF NOT EXISTS idx_repeaters_mode ON repeaters(mode);
CREATE INDEX IF NOT EXISTS idx_repeaters_band ON repeaters(band);
CREATE INDEX IF NOT EXISTS idx_repeaters_status ON repeaters(status);
CREATE INDEX IF NOT EXISTS idx_repeaters_canton ON repeaters(canton);
CREATE INDEX IF NOT EXISTS idx_repeaters_callsign ON repeaters(callsign);
CREATE INDEX IF NOT EXISTS idx_repeaters_output_frequency ON repeaters(output_frequency);

-- Table for repeater activity scan results
CREATE TABLE IF NOT EXISTS repeater_activity (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,

    -- Links to parent tables
    capture_id INTEGER NOT NULL REFERENCES captures(id) ON DELETE CASCADE,
    repeater_id INTEGER REFERENCES repeaters(id) ON DELETE SET NULL,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    scan_start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    scan_end_time TIMESTAMP WITH TIME ZONE NOT NULL,
    scan_duration_seconds INTEGER NOT NULL CHECK (scan_duration_seconds > 0),

    -- Frequency (denormalized for queries when repeater deleted)
    frequency BIGINT NOT NULL CHECK (frequency > 0),

    -- Activity metrics
    carrier_detected BOOLEAN NOT NULL DEFAULT FALSE,
    transmission_count INTEGER NOT NULL DEFAULT 0 CHECK (transmission_count >= 0),
    total_active_seconds DECIMAL(10, 2) NOT NULL DEFAULT 0 CHECK (total_active_seconds >= 0),
    activity_percentage DECIMAL(5, 2) NOT NULL DEFAULT 0 CHECK (activity_percentage >= 0 AND activity_percentage <= 100),

    -- Signal quality metrics
    average_signal_strength DECIMAL(8, 2),  -- RMS power in dB
    peak_signal_strength DECIMAL(8, 2),
    noise_floor DECIMAL(8, 2),

    -- Transmission details (JSON array)
    transmissions JSONB,  -- [{start_offset: 12.5, duration: 3.2, avg_strength: -45, peak_strength: -42}, ...]

    -- Raw analysis data
    analysis_data JSONB
);

-- Indices for repeater_activity
CREATE INDEX IF NOT EXISTS idx_repeater_activity_capture_id ON repeater_activity(capture_id);
CREATE INDEX IF NOT EXISTS idx_repeater_activity_repeater_id ON repeater_activity(repeater_id);
CREATE INDEX IF NOT EXISTS idx_repeater_activity_created_at ON repeater_activity(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_repeater_activity_frequency ON repeater_activity(frequency);
CREATE INDEX IF NOT EXISTS idx_repeater_activity_carrier ON repeater_activity(carrier_detected);
CREATE INDEX IF NOT EXISTS idx_repeater_activity_scan_start ON repeater_activity(scan_start_time DESC);

-- JSONB indices for repeater_activity
CREATE INDEX IF NOT EXISTS idx_repeater_activity_transmissions_gin ON repeater_activity USING gin(transmissions);
CREATE INDEX IF NOT EXISTS idx_repeater_activity_analysis_gin ON repeater_activity USING gin(analysis_data);

-- Table for tracking full repeater scan sessions
CREATE TABLE IF NOT EXISTS repeater_scan_sessions (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,

    -- Scan parameters
    scan_duration_per_repeater INTEGER NOT NULL CHECK (scan_duration_per_repeater > 0),  -- seconds
    repeaters_scanned INTEGER NOT NULL DEFAULT 0 CHECK (repeaters_scanned >= 0),
    repeaters_with_activity INTEGER NOT NULL DEFAULT 0 CHECK (repeaters_with_activity >= 0),

    -- Time tracking
    scan_start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    scan_end_time TIMESTAMP WITH TIME ZONE,
    total_duration_seconds INTEGER CHECK (total_duration_seconds >= 0),

    -- Status
    status VARCHAR(20) DEFAULT 'in_progress' CHECK (status IN ('in_progress', 'completed', 'failed', 'cancelled')),

    -- Metadata
    metadata JSONB
);

-- Indices for repeater_scan_sessions
CREATE INDEX IF NOT EXISTS idx_scan_sessions_created_at ON repeater_scan_sessions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_scan_sessions_status ON repeater_scan_sessions(status);
CREATE INDEX IF NOT EXISTS idx_scan_sessions_scan_start ON repeater_scan_sessions(scan_start_time DESC);

-- Create triggers for updated_at on repeaters
CREATE TRIGGER update_repeaters_updated_at
    BEFORE UPDATE ON repeaters
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Create view for statistics
CREATE OR REPLACE VIEW capture_statistics AS
SELECT
    COUNT(*) as total_captures,
    COUNT(CASE WHEN transcription_text IS NOT NULL AND transcription_text != '' THEN 1 END) as successful_transcriptions,
    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_captures,
    COUNT(DISTINCT frequency) as unique_frequencies,
    COUNT(DISTINCT language) as unique_languages,
    DATE(created_at) as capture_date
FROM captures
GROUP BY DATE(created_at)
ORDER BY capture_date DESC;

-- Create view for recent captures
CREATE OR REPLACE VIEW recent_captures AS
SELECT
    id,
    uuid,
    created_at,
    frequency,
    modulation,
    duration,
    language,
    LEFT(transcription_text, 100) as text_preview,
    language_confidence,
    status
FROM captures
ORDER BY created_at DESC
LIMIT 100;

-- Create view for frequency usage
CREATE OR REPLACE VIEW frequency_usage AS
SELECT
    frequency,
    COUNT(*) as capture_count,
    MAX(created_at) as last_used,
    ARRAY_AGG(DISTINCT modulation) as modulations_used
FROM captures
GROUP BY frequency
ORDER BY capture_count DESC;

-- Create view for APRS statistics
CREATE OR REPLACE VIEW aprs_statistics AS
SELECT
    COUNT(*) as total_packets,
    COUNT(DISTINCT source_callsign) as unique_callsigns,
    COUNT(DISTINCT capture_id) as total_captures,
    COUNT(CASE WHEN latitude IS NOT NULL THEN 1 END) as packets_with_position,
    DATE(created_at) as packet_date
FROM aprs_messages
GROUP BY DATE(created_at)
ORDER BY packet_date DESC;

-- Create view for POCSAG statistics
CREATE OR REPLACE VIEW pocsag_statistics AS
SELECT
    COUNT(*) as total_messages,
    COUNT(DISTINCT address) as unique_addresses,
    COUNT(DISTINCT capture_id) as total_captures,
    COUNT(CASE WHEN message_type = 'alphanumeric' THEN 1 END) as alphanumeric_messages,
    COUNT(CASE WHEN message_type = 'numeric' THEN 1 END) as numeric_messages,
    COUNT(CASE WHEN message_type = 'tone' THEN 1 END) as tone_messages,
    COUNT(CASE WHEN baud_rate = 512 THEN 1 END) as messages_512,
    COUNT(CASE WHEN baud_rate = 1200 THEN 1 END) as messages_1200,
    COUNT(CASE WHEN baud_rate = 2400 THEN 1 END) as messages_2400,
    DATE(created_at) as message_date
FROM pocsag_messages
GROUP BY DATE(created_at)
ORDER BY message_date DESC;

-- Create view for repeater activity statistics
CREATE OR REPLACE VIEW repeater_activity_statistics AS
SELECT
    COUNT(DISTINCT ra.repeater_id) as total_repeaters_scanned,
    COUNT(DISTINCT CASE WHEN ra.carrier_detected THEN ra.repeater_id END) as repeaters_with_activity,
    COUNT(*) as total_scans,
    SUM(ra.transmission_count) as total_transmissions,
    AVG(ra.activity_percentage) as avg_activity_percentage,
    AVG(ra.average_signal_strength) as avg_signal_strength,
    DATE(ra.created_at) as scan_date
FROM repeater_activity ra
GROUP BY DATE(ra.created_at)
ORDER BY scan_date DESC;

-- Insert initial metadata
INSERT INTO captures (
    frequency,
    modulation,
    duration,
    gain,
    audio_file_path,
    transcription_text,
    language,
    language_confidence,
    status
) VALUES (
    0,
    'FM',
    0,
    0,
    '/app/recordings/placeholder.wav',
    'Database initialized successfully',
    'en',
    1.0,
    'completed'
) ON CONFLICT DO NOTHING;

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO radio_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO radio_user;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO radio_user;

-- Display initialization message
DO $$
BEGIN
    RAISE NOTICE 'Radio Monitoring Database initialized successfully!';
    RAISE NOTICE 'Database: radio_monitoring';
    RAISE NOTICE 'User: radio_user';
    RAISE NOTICE 'Tables created: captures, aprs_messages, pocsag_messages';
    RAISE NOTICE 'Views created: capture_statistics, recent_captures, frequency_usage, aprs_statistics, pocsag_statistics';
    RAISE NOTICE 'APRS support: enabled';
    RAISE NOTICE 'POCSAG support: enabled';
END $$;
