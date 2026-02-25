import { useEventBus } from "@vueuse/core";

export const serverEventBus = useEventBus<'event'>('server-events')

// let sourceInstance : EventSource | undefined = undefined
let polling = false

const source = () => {
	if (polling === false) {
		const url = `${import.meta.env.VITE_EVENTSOURCE}/events`
		console.log(`connecting to ${url}`)

		setInterval(async () => {
			const results = await fetch(url).then(res => res.json())

		}, 15_000)

		polling = true
	}
}

const waitForEvent = <T>(matcher : (data : T) => boolean, timeout: number = 20_000) => new Promise((resolve, reject) => {

	const off = serverEventBus.on(data => {
		if (matcher(data as T)) {
			off()
			clearTimeout(timeoutId)
			resolve(data)
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
