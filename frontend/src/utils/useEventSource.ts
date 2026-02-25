import { useEventBus } from "@vueuse/core";

export const serverEventBus = useEventBus<'event'>('server-events')

let sourceInstance : EventSource | undefined = undefined

const source = () => {
	if (sourceInstance === undefined) {
		console.log(`connecting to ${import.meta.env.VITE_EVENTSOURCE}`)
		sourceInstance = new EventSource(import.meta.env.VITE_EVENTSOURCE)

		sourceInstance.onerror = (error) => {
			console.log(error)
		}

		sourceInstance.onmessage = event => {
			console.log(event)
			const data = JSON.parse(event.data)
			console.log(data)

			serverEventBus.emit('event', data)
		}
	}

	return sourceInstance
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
