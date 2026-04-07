<script lang="ts">
  import { T, useFrame } from '@threlte/core';
  export let isLive = false;
  export let color = '#00d4ff';

  let rotationY = 0;
  let rotationX = 0;

  // useFrame chạy 60fps để xử lý vật lý
  useFrame((state, delta) => {
    // Nếu API đang gọi (isLive = true), gia tốc quay tăng gấp 10 lần
    const speedMultiplier = isLive ? 10 : 0.5;
    rotationY += delta * speedMultiplier;
    rotationX += delta * (speedMultiplier * 0.3);
  });
</script>

<T.AmbientLight intensity={0.2} />
<T.PointLight position={[10, 10, 10]} intensity={1.5} color={isLive ? "#ff0055" : color} />

<T.Mesh rotation.y={rotationY} rotation.x={rotationX}>
  <T.IcosahedronGeometry args={[2, 1]} />
  <T.MeshStandardMaterial 
    color={isLive ? "#ff0055" : color} 
    wireframe={true} 
    emissive={isLive ? "#ff0033" : color}
    emissiveIntensity={isLive ? 2 : 0.5}
  />
</T.Mesh>
