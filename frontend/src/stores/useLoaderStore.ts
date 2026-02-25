import { ref } from 'vue'
import { defineStore } from 'pinia'

export interface LoaderTask {
	id: string
	label: string
	completed: boolean
}

export const useLoaderStore = defineStore('loader', () => {
	const isOpen = ref(false)
	const message = ref('')
	const tasks = ref<LoaderTask[]>([])

	function open(loadingMessage: string = 'Loading...', taskList?: { id: string; label: string }[]) {
		message.value = loadingMessage
		tasks.value = taskList?.map(t => ({ ...t, completed: false })) ?? []
		isOpen.value = true
	}

	function completeTask(taskId: string) {
		const task = tasks.value.find(t => t.id === taskId)
		if (task) {
			task.completed = true
		}
	}

	function close() {
		isOpen.value = false
		message.value = ''
		tasks.value = []
	}

	return {
		isOpen,
		message,
		tasks,
		open,
		completeTask,
		close
	}
})
