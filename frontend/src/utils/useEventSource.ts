import { useEventBus } from "@vueuse/core";

export const serverEventBus = useEventBus<'event'>('server-events')

// let sourceInstance : EventSource | undefined = undefined
let polling = false

const source = () => {
	if (polling === false) {
		const url = `${import.meta.env.VITE_EVENTSOURCE}/events`
		console.log(`connecting to ${url}`)

		setInterval(async () => {
			try {
				const results = await fetch(url).then(res => res.json())
				if (results) {
					serverEventBus.emit(results)
				}
			} catch (error) {
				console.error('Failed to fetch events:', error)
			}
		}, 1_000)

		polling = true
	}
}

const waitForEvent = <T>(matcher : (data : T) => boolean, timeout: number = 200_000) => new Promise((resolve, reject) => {

	const off = serverEventBus.on(data => {
		const match = (data as unknown as T[]).find(matcher)

		console.log(match)

		if (match) {
			off()
			clearTimeout(timeoutId)
			resolve(match)
		}
	})

	const timeoutId = setTimeout(() => {
		reject('wait timed out')
		off()
	}, timeout)
})

export function useEventSource() {
	return {
		initialize: () => {
			source()
		},
		serverEventBus,
		waitForEvent
	}
}
