<script setup lang="ts">
import { useLoaderStore } from '@/stores/useLoaderStore'
import logoImage from '@/assets/logo.png'

const loaderStore = useLoaderStore()
</script>

<template>
	<Teleport to="body">
		<Transition name="fade">
			<div
				v-if="loaderStore.isOpen"
				class="fixed inset-0 z-50 flex flex-col items-center justify-center bg-white/80"
			>
				<div role="status" class="loader-container">
					<img
						:src="logoImage"
						alt="Loading"
						class="w-24 h-24 object-contain animate-pulse-bounce"
					/>
					<span class="sr-only">Loading...</span>
				</div>
				<p class="mt-4 text-black text-2xl">{{ loaderStore.message }}</p>
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
