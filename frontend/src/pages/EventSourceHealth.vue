<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { FwbButton } from 'flowbite-vue'
import { useEventSource } from '@/utils/useEventSource'
import { ulid } from 'ulid'

interface EventEntry {
	id: string
	timestamp: Date
	data: unknown
}

const events = ref<EventEntry[]>([])
const isConnected = ref(false)

const { initialize, serverEventBus } = useEventSource()

function formatTimestamp(date: Date): string {
	return date.toLocaleTimeString('en-US', {
		hour: '2-digit',
		minute: '2-digit',
		second: '2-digit',
		hour12: false
	})
}

function formatJson(data: unknown): string {
	try {
		return JSON.stringify(data, null, 2)
	} catch {
		return String(data)
	}
}

function clearEvents() {
	events.value = []
}

const unsubscribe = serverEventBus.on((event) => {
	events.value.unshift({
		id: ulid(),
		timestamp: new Date(),
		data: event
	})
})

onMounted(() => {
	initialize()
	isConnected.value = true
})

onUnmounted(() => {
	unsubscribe()
})
</script>

<template>
	<div class="w-full">
		<div class="bg-[#F1F1F1] border border-[#CCCCCC] rounded-xl p-6">
			<div class="flex items-center justify-between mb-4">
				<div class="flex items-center gap-4">
					<h1 class="text-xl font-bold text-gray-900">EventSource Monitor</h1>
					<div class="flex items-center gap-2">
						<span
							:class="[
								'w-3 h-3 rounded-full',
								isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'
							]"
						></span>
						<span class="text-sm text-gray-600">
							{{ isConnected ? 'Listening' : 'Disconnected' }}
						</span>
					</div>
				</div>
				<div class="flex items-center gap-2">
					<span class="text-sm text-gray-500">{{ events.length }} events</span>
					<FwbButton color="light" @click="clearEvents" class="cursor-pointer">
						Clear
					</FwbButton>
				</div>
			</div>

			<div class="border border-gray-200 rounded-lg bg-white max-h-150 overflow-y-auto">
				<div v-if="events.length === 0" class="p-8 text-center text-gray-500">
					Waiting for events...
				</div>
				<div v-else class="divide-y divide-gray-200">
					<div
						v-for="event in events"
						:key="event.id"
						class="p-4 hover:bg-gray-50 transition-colors"
					>
						<div class="flex items-center gap-2 mb-2">
							<span class="text-xs font-mono bg-gray-100 px-2 py-1 rounded text-gray-600">
								{{ formatTimestamp(event.timestamp) }}
							</span>
						</div>
						<pre class="text-sm font-mono bg-gray-900 text-green-400 p-3 rounded overflow-x-auto">{{ formatJson(event.data) }}</pre>
					</div>
				</div>
			</div>
		</div>
	</div>
</template>
