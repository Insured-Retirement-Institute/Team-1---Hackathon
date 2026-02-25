<script setup lang="ts">
import { useLoaderStore } from '@/stores/useLoaderStore'
import logoImage from '@/assets/logo-eye.png'
import CheckCircleFilledIcon from '@/icons/CheckCircleFilledIcon.svg'
import SpinnerIcon from '@/icons/SpinnerIcon.svg'

const loaderStore = useLoaderStore()
</script>

<template>
	<Teleport to="body">
		<Transition name="fade">
			<div
				v-if="loaderStore.isOpen"
				class="fixed inset-0 z-50 flex flex-col items-center justify-center bg-white/90"
			>
				<div role="status" class="loader-container">
					<img
						:src="logoImage"
						alt="Loading"
						class="w-48 h-48 object-contain animate-pulse-bounce"
					/>
					<span class="sr-only">Loading...</span>
				</div>
				<p class="mt-4 text-black text-2xl">{{ loaderStore.message }}</p>

				<!-- Task List -->
				<ul v-if="loaderStore.tasks.length > 0" class="mt-6 space-y-3">
					<li
						v-for="task in loaderStore.tasks"
						:key="task.id"
						class="flex items-center gap-3 text-lg"
					>
						<!-- Spinner for incomplete -->
						<SpinnerIcon
							v-if="!task.completed"
							class="animate-spin h-8 w-8 text-blue-600"
						/>
						<!-- Check mark for completed -->
						<CheckCircleFilledIcon
							v-else
							class="h-8 w-8 text-green-600"
						/>
						<span class="text-xl">
							{{ task.label }}
						</span>
					</li>
				</ul>
			</div>
		</Transition>
	</Teleport>
</template>

<style scoped>
@keyframes pulse-bounce {
	0%, 100% {
		transform: scale(1);
		opacity: 1;
	}
	50% {
		transform: scale(1.15);
		opacity: 0.8;
	}
}

.animate-pulse-bounce {
	animation: pulse-bounce 1s ease-in-out infinite;
}
</style>
