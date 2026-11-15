// Native buttons provide a keyboard and single-pointer alternative to dragging/pinching.
export function adjustCamera(atlas,action) {
  if(!atlas)return;
  switch(action) {
    case 'left': atlas.yaw-=10;break;
    case 'right': atlas.yaw+=10;break;
    case 'up': atlas.pitch=Math.min(85,Math.max(-65,atlas.pitch+5));break;
    case 'down': atlas.pitch=Math.min(85,Math.max(-65,atlas.pitch-5));break;
    case 'in': atlas.scaleZoom(1.15);break;
    case 'out': atlas.scaleZoom(1/1.15);break;
    default:return;
  }
  atlas.draw();
}
