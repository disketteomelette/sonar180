#include <Servo.h>
#define SP 9
#define TP 8
#define EP 7
#define SD 1
#define MD 15
#define TO1 15000UL
#define TO2 60000UL

Servo s;
static inline void trig(){digitalWrite(TP,0);delayMicroseconds(2);digitalWrite(TP,1);delayMicroseconds(10);digitalWrite(TP,0);}
static inline bool wH(unsigned long to){unsigned long t=micros();while(!digitalRead(EP)) if(micros()-t>=to) return 0; return 1;}
static inline unsigned long mH(unsigned long to){unsigned long t=micros();while(digitalRead(EP)) if(micros()-t>=to) return 0; return micros()-t;}

long dist(){
  unsigned long t=micros(); while(digitalRead(EP)) if(micros()-t>2000) break;
  trig();
  if(!wH(TO1)){unsigned long ex=TO2>TO1?TO2-TO1:0; if(!ex||!wH(ex)) return -1;}
  unsigned long d=mH(TO2); return d? (long)(d/58): -1;
}

void sendAt(int a){
  static int la=0;
  s.write(a);
  int d=a-la; if(d<0)d=-d;
  int w=8+2*d; if(w>MD) w=MD; delay(w);
  la=a;
  Serial.print(a); Serial.print(':'); Serial.println(dist());
}

void setup(){
  Serial.begin(115200);
  pinMode(TP,OUTPUT); pinMode(EP,INPUT);
  s.attach(SP); s.write(0); delay(300);
}

void loop(){
  for(int a=0;a<=180;a+=SD) sendAt(a);
  for(int a=180;a>=0;a-=SD) sendAt(a);
}

