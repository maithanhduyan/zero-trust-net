import { useEffect, useRef, useCallback, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

export interface WebSocketMessage {
    type: string
    event_type?: string
    data?: Record<string, unknown>
    timestamp?: string
}

interface UseWebSocketOptions {
    onMessage?: (message: WebSocketMessage) => void
    onConnect?: () => void
    onDisconnect?: () => void
    onError?: (error: Event) => void
    reconnectAttempts?: number
    reconnectInterval?: number
}

export function useWebSocket(url: string, options: UseWebSocketOptions = {}) {
    const {
        onMessage,
        onConnect,
        onDisconnect,
        onError,
        reconnectAttempts = 5,
        reconnectInterval = 3000,
    } = options

    const wsRef = useRef<WebSocket | null>(null)
    const reconnectCount = useRef(0)
    const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
    const [isConnected, setIsConnected] = useState(false)
    const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null)
    const queryClient = useQueryClient()

    const connect = useCallback(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            return
        }

        try {
            wsRef.current = new WebSocket(url)

            wsRef.current.onopen = () => {
                console.log('[WebSocket] Connected')
                setIsConnected(true)
                reconnectCount.current = 0
                onConnect?.()
            }

            wsRef.current.onclose = () => {
                console.log('[WebSocket] Disconnected')
                setIsConnected(false)
                onDisconnect?.()

                // Attempt reconnect
                if (reconnectCount.current < reconnectAttempts) {
                    reconnectCount.current++
                    console.log(`[WebSocket] Reconnecting... (attempt ${reconnectCount.current})`)
                    reconnectTimer.current = setTimeout(connect, reconnectInterval)
                }
            }

            wsRef.current.onerror = (error) => {
                console.error('[WebSocket] Error:', error)
                onError?.(error)
            }

            wsRef.current.onmessage = (event) => {
                try {
                    const message: WebSocketMessage = JSON.parse(event.data)
                    setLastMessage(message)
                    onMessage?.(message)

                    // Auto-invalidate queries based on event type
                    if (message.event_type) {
                        handleEventInvalidation(message.event_type, queryClient)
                    }
                } catch (e) {
                    console.error('[WebSocket] Failed to parse message:', e)
                }
            }
        } catch (error) {
            console.error('[WebSocket] Connection error:', error)
        }
    }, [url, onConnect, onDisconnect, onError, onMessage, reconnectAttempts, reconnectInterval, queryClient])

    const disconnect = useCallback(() => {
        if (reconnectTimer.current) {
            clearTimeout(reconnectTimer.current)
        }
        reconnectCount.current = reconnectAttempts // Prevent reconnection
        wsRef.current?.close()
        wsRef.current = null
        setIsConnected(false)
    }, [reconnectAttempts])

    const sendMessage = useCallback((message: WebSocketMessage) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify(message))
        } else {
            console.warn('[WebSocket] Cannot send message - not connected')
        }
    }, [])

    useEffect(() => {
        connect()
        return () => {
            disconnect()
        }
    }, [connect, disconnect])

    return {
        isConnected,
        lastMessage,
        sendMessage,
        connect,
        disconnect,
    }
}

// Handle query invalidation based on event type
function handleEventInvalidation(eventType: string, queryClient: ReturnType<typeof useQueryClient>) {
    const invalidationMap: Record<string, string[]> = {
        // Node events
        'node.registered': ['nodes'],
        'node.approved': ['nodes'],
        'node.suspended': ['nodes'],
        'node.revoked': ['nodes'],
        'node.heartbeat': ['nodes'],
        'node.trust_updated': ['nodes'],

        // Client events
        'client.created': ['clients'],
        'client.revoked': ['clients'],
        'client.config_downloaded': ['clients'],

        // User events
        'user.created': ['users'],
        'user.updated': ['users'],
        'user.deleted': ['users'],

        // Group events
        'group.created': ['groups'],
        'group.deleted': ['groups'],
        'group.member_added': ['groups', 'users'],
        'group.member_removed': ['groups', 'users'],

        // Policy events
        'policy.created': ['policies'],
        'policy.deleted': ['policies'],
        'policy.updated': ['policies'],

        // All events should update the events list
    }

    const queriesToInvalidate = invalidationMap[eventType] || []

    // Always invalidate events
    queriesToInvalidate.push('events')

    queriesToInvalidate.forEach((queryKey) => {
        queryClient.invalidateQueries({ queryKey: [queryKey] })
    })
}

// Hook for admin WebSocket connection
export function useAdminWebSocket() {
    const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/admin`

    return useWebSocket(wsUrl, {
        onConnect: () => {
            console.log('[Admin WS] Connected to admin channel')
        },
        onMessage: (message) => {
            console.log('[Admin WS] Received:', message)
        },
    })
}

// Hook for agent WebSocket connection (if needed for monitoring)
export function useAgentWebSocket(hostname: string, token: string) {
    const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/agent?hostname=${hostname}&token=${token}`

    return useWebSocket(wsUrl)
}

export default useWebSocket
