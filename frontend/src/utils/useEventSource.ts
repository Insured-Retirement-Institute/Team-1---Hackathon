import { useEventBus } from "@vueuse/core";

export const serverEventBus = useEventBus<'event'>('server-events')

let sourceInstance : EventSource | undefined = undefined

const source = () => {
	if (sourceInstance === undefined) {
		sourceInstance = new EventSource('https://sse.dev/test?interval=5')

		sourceInstance.onmessage = event => {
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
