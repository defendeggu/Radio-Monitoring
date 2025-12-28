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

-- Add mode column for APRS support
ALTER TABLE captures ADD COLUMN IF NOT EXISTS mode VARCHAR(20) DEFAULT 'voice'
    CHECK (mode IN ('voice', 'aprs'));

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
    RAISE NOTICE 'Tables created: captures, aprs_messages';
    RAISE NOTICE 'Views created: capture_statistics, recent_captures, frequency_usage, aprs_statistics';
    RAISE NOTICE 'APRS support: enabled';
END $$;
