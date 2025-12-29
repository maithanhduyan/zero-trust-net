-- Migration: Add agent integrity verification columns
-- Date: 2025-12-29
-- Description: Adds columns to track agent file hashes for integrity verification

-- Add integrity-related columns to nodes table
ALTER TABLE nodes ADD COLUMN agent_hash VARCHAR(64);
ALTER TABLE nodes ADD COLUMN last_reported_hash VARCHAR(64);
ALTER TABLE nodes ADD COLUMN hash_verified BOOLEAN DEFAULT FALSE NOT NULL;
ALTER TABLE nodes ADD COLUMN hash_mismatch_count INTEGER DEFAULT 0 NOT NULL;

-- Add comments for documentation
-- agent_hash: Expected SHA-256 hash of agent files (set by admin)
-- last_reported_hash: Last hash reported by agent in heartbeat
-- hash_verified: Whether agent hash matches expected
-- hash_mismatch_count: Consecutive hash mismatches (0 = verified)

-- Create index for quick lookup of unverified nodes
CREATE INDEX IF NOT EXISTS ix_nodes_hash_verified ON nodes(hash_verified);

-- Note: Run this migration with:
-- sqlite3 zerotrust.db < 002_add_agent_integrity.sql
