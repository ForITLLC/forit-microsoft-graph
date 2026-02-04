import * as fs from 'fs';
import * as path from 'path';

const LOG_FILE = '/tmp/mcp-tool-calls.log';
const MAX_LOG_SIZE = 5 * 1024 * 1024; // 5MB

interface LogEntry {
    ts: string;
    mcp: string;
    tool: string;
    conn: string | null;
    project: string | null;
    session: string | null;
    args: Record<string, any>;
    result?: string;
    error?: string;
    duration_ms?: number;
}

function rotateIfNeeded(): void {
    try {
        if (fs.existsSync(LOG_FILE)) {
            const stats = fs.statSync(LOG_FILE);
            if (stats.size > MAX_LOG_SIZE) {
                const backup = LOG_FILE + '.1';
                if (fs.existsSync(backup)) fs.unlinkSync(backup);
                fs.renameSync(LOG_FILE, backup);
            }
        }
    } catch (e) {
        // Ignore rotation errors
    }
}

function sanitizeArgs(args: Record<string, any>): Record<string, any> {
    const sensitiveKeys = ['password', 'secret', 'token', 'key', 'credential', 'confirmation'];
    const safe: Record<string, any> = {};

    for (const [k, v] of Object.entries(args)) {
        if (sensitiveKeys.some(s => k.toLowerCase().includes(s))) {
            safe[k] = '[REDACTED]';
        } else if (typeof v === 'string' && v.length > 100) {
            safe[k] = v.substring(0, 100) + '...';
        } else {
            safe[k] = v;
        }
    }
    return safe;
}

export function logToolCall(
    mcpName: string,
    toolName: string,
    args: Record<string, any>,
    connectionName?: string,
    result?: string,
    error?: string,
    durationMs?: number
): void {
    try {
        rotateIfNeeded();

        const project = path.basename(process.cwd());
        const sessionId = process.env.CLAUDE_SESSION_ID || process.env.MCP_SESSION_ID || null;

        const entry: LogEntry = {
            ts: new Date().toISOString(),
            mcp: mcpName,
            tool: toolName,
            conn: connectionName || null,
            project,
            session: sessionId,
            args: sanitizeArgs(args),
        };

        if (result) entry.result = result.substring(0, 200);
        if (error) entry.error = error.substring(0, 500);
        if (durationMs !== undefined) entry.duration_ms = durationMs;

        fs.appendFileSync(LOG_FILE, JSON.stringify(entry) + '\n');
    } catch (e) {
        // Don't let logging errors break the MCP
    }
}
