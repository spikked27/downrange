const assert=require('node:assert/strict');
const sky=require('../app/static/observer.js');
let checks=0;
function near(actual,expected,tolerance=1e-7){assert(Math.abs(actual-expected)<tolerance,`${actual} != ${expected}`);checks++;}
function camera(azimuth=0,elevation=0,fov=90){return {azimuth,elevation,fov};}
near(Math.hypot(...sky.vector(25,70)),1);
assert.deepEqual(sky.vector(0,0),[0,1,0]);checks++;
for(const az of [0,45,90,180,270,359]){
 for(const el of [-10,0,20,60,89]){
  const c=camera(az,el),p=sky.project(az,el,c,800,400);
  near(p.x,400);near(p.y,200);
  const ray=sky.unproject(p.x,p.y,c,800,400);
  near(((ray.azimuth-az+540)%360)-180,0);near(ray.elevation,el);
 }
}
assert(sky.project(10,0,camera(),800,400).x>400);checks++;
assert(sky.project(350,0,camera(),800,400).x<400);checks++;
near(sky.project(45,0,camera(),800,400).x,800);
near(sky.project(-45,0,camera(),800,400).x,0);
assert(sky.project(180,0,camera(),800,400)===null);checks++;
assert(sky.project(90,0,camera(),800,400)===null);checks++;
near(sky.project(0,0,camera(0,20),800,400).y,200+400*Math.tan(20*Math.PI/180));
assert(sky.project(0,30,camera(0,20),800,400).y<200);checks++;
for(const az of [0,90,180,270]){
 const c=camera(az,15,80);
 for(const [x,y] of [[0,0],[400,200],[800,400],[630,175]]){
  const ray=sky.unproject(x,y,c,800,400),p=sky.project(ray.azimuth,ray.elevation,c,800,400);
  near(p.x,x,1e-5);near(p.y,y,1e-5);
 }
}
const f=sky.circularFrame([350,355,0,5,10]);near(f.center,0);near(f.span,20);
near(sky.circularFrame([40]).center,40);near(sky.circularFrame([40]).span,0);
const points=[{azimuth:155,elevation:5,ordinary:true},{azimuth:180,elevation:30,ordinary:true},{azimuth:200,elevation:10,ordinary:true}];
const fitted=sky.framePath(points,800,400);
for(const p of points){assert(sky.project(p.azimuth,p.elevation,fitted,800,400).inFrame);checks++;}
const north=sky.framePath([{azimuth:355,elevation:10,ordinary:true},{azimuth:5,elevation:20,ordinary:true}],400,310);
assert(north.azimuth<10||north.azimuth>350);checks++;
assert(Number.isFinite(sky.project(0,90,camera(270,89),400,310).y));checks++;
assert.equal(sky.markerState({elevation:-2,ordinary:true},5),'below_horizon');checks++;
assert.equal(sky.markerState({elevation:2,ordinary:true},5),'below_limit');checks++;
assert.equal(sky.markerState({elevation:10,ordinary:true},5),'powered');checks++;
assert.equal(sky.markerState({elevation:10,jellyfish:true},5),'plume');checks++;
assert.equal(sky.markerState({elevation:10,ordinary:false,jellyfish:false},5),'unassessed');checks++;
assert.equal(sky.markerState(null,5),'no_data');checks++;
assert.equal(sky.project(NaN,0,camera(),400,300),null);checks++;
assert.equal(sky.project(0,0,camera(0,0,180),400,300),null);checks++;
console.log(`Observer perspective: ${checks} coordinate, projection, horizon, north-wrap and marker-state assertions passed.`);
