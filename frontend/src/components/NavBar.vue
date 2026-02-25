<script setup lang="ts">
import { FwbButton } from 'flowbite-vue';
import logoImage from '@/assets/logo.png'
import avatarImage from '@/assets/avatar.png'
import BellIcon from '@/icons/BellIcon.svg'
import { RouterLink } from 'vue-router';
</script>

<template>
	<div>
		<nav class="flex items-center justify-between p-8">
			<RouterLink to="/">
				<div class="flex items-center gap-2">
					<img :src="logoImage" class="w-8"/>
					<p class="font-extrabold text-2xl">Cha-Cha-Cha Changes</p>
				</div>
			</RouterLink>

			<div class="flex items-center gap-2">
				<FwbButton color="default">Logout</FwbButton>
				<button>
					<BellIcon />
				</button>
				<button>
					<img :src="avatarImage" />
				</button>
			</div>
		</nav>
	</div>
</template>
