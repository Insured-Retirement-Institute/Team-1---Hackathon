<script setup lang="ts">
import { FwbButton } from 'flowbite-vue';
import { useRoute, useRouter } from 'vue-router';
import AppLoader from '@/components/AppLoader.vue';
import type { RouteMeta } from '@/router';
import { awsTest } from './api/Api';
import NavBar from './components/NavBar.vue';

const route = useRoute()
const router = useRouter()

async function handleNavigation(meta: RouteMeta) {
	if (meta.handler) {
		await meta.handler()
	}
	router.push(meta.route)
}

awsTest()
</script>

<template>
	<div class="flex flex-col h-screen">
		<AppLoader />
		<NavBar />
		<div class="flex flex-wrap w-full *:p-2 grow overflow-auto p-10">
			<RouterView v-slot="{ Component }">
				<Transition name="fade">
					<component :is="Component"/>
				</Transition>
			</RouterView>
		</div>

		<div class="flex w-full gap-4 justify-center items-center p-5">
			<FwbButton
				v-if="route.meta.previous"
				color="default"
				@click="handleNavigation(route.meta.previous as RouteMeta)"
				class="cursor-pointer"
			>Back</FwbButton>

			<FwbButton
				v-if="route.meta.next"
				color="default"
				@click="handleNavigation(route.meta.next as RouteMeta)"
				class="cursor-pointer"
			>Next</FwbButton>
		</div>
	</div>
</template>
