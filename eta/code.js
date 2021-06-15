// Copyright 2015-2021 Jerónimo Barraco Mármol GPL v3

var _eta = {
	to: 1000,//timeout
	c: 0,//count
	st: 0, //start time
	s: 0,//sum
	l: 0,//last ms
	ld: 0,//last dur
	a: 0,//avg
	o: 0,//objective
	e: 0,//eta
	sp: 0,//speed
	cs: 0,//current sp
	ca: 0,//current avg
	ce: 0,//current eta
	timer: 0,
	stop(){
		clearTimeout(_eta.timer);
		_eta.timer = 0;
		_eta.setCountBtnText("Continue");
		document.getElementById("b_reset").value = "Start";
	},
	tick(){
		_eta.timer = setTimeout(_eta.tick, _eta.to);
		let n = +(new Date());
		_eta.cs = n - _eta.l;
		_eta.ca = (_eta.s + _eta.cs)/_eta.c;
		_eta.ce = (_eta.o -_eta.c)*_eta.ca;
		_eta.e = ((_eta.o -_eta.c)*_eta.a)-_eta.cs;
		_eta.show();
	},
	count(){
		//start if never started
		if (_eta.st==0){
			_eta.reset();
			return;
		}

		// restart the timer if its stopped
		if(_eta.timer == 0) {
			_eta.tick();
			_eta.setCountBtnText("Count");
			return;
		}

		let n = +(new Date());
		_eta.ld = n - _eta.l;
		_eta.l = n;
		_eta.c += 1;
		// _eta.s += _eta.ld; might be less accurate 
		_eta.s = (_eta.l - _eta.st);// might be more accurate 
		_eta.a = _eta.s/_eta.c;
		_eta.show();
		
		if(_eta.c == _eta.o) _eta.stop(); // stop when target reached


		// on count set load's count value
		document.getElementById("start_count").value = _eta.c;
		// and last ms
		document.getElementById("last_ms").value = _eta.l; 
		_eta.saveToUrl(); // write url
	},
	reset(){
		_eta.stop();
		_eta.c = 0;
		_eta.e = 0;//eta
		_eta.s = 0;//sum
		_eta.a = 0;//avg
		_eta.l = 0;//last ms
		_eta.ld = 0;//last_duration
		_eta.sp = 0;//speed
		_eta.cs = 0;//current sp
		_eta.ca = 0;//current avg
		_eta.ce = 0;//current eta
		_eta.o = parseInt(document.getElementById("cant").value);
		_eta.to = parseInt(document.getElementById("toms").value);
		_eta.l = +new Date(); //last: gets current milliseconds. meh
		_eta.st = _eta.l; //start ms
		_eta.tick();

		_eta.setCountBtnText("Count");
		document.getElementById("b_reset").value = "Restart";

		// beware conflicts with load
		document.getElementById("start_ms").value = _eta.st;
	},
	load() {
		let sms = parseInt( document.getElementById("start_ms").value);
		_eta.reset(); //last is set to now, that's ok (kinda) 
		// restore original startms
		document.getElementById("start_ms").value = sms;

		_eta.c = parseInt(document.getElementById("start_count").value);
		_eta.st = sms;

		// try to load last ms if possible otherwise reset above makes it default to now 
		let nl = parseInt(document.getElementById("last_ms").value);
		if (!isNaN(nl) && nl > 0 && nl > _eta.st) _eta.l = nl;

		_eta.s = (_eta.l - _eta.st);

		_eta.a = _eta.s/_eta.c;
		_eta.ld = _eta.a;
	},
	setCountBtnText(t) {
		document.getElementById("b_count").value = t;
	},
	ms2td(v, simple){
		v = Math.ceil(v);
		let t = "";

		let ms = v %1000;
		v -= ms;
		v /= 1000;

		let s = v %60;
		v -= s;
		v /= 60;

		let m = v %60;
		v -= m;
		v /= 60;

		let h = v %24;
		v -= h;
		v /= 24;

		t = h + ":" + m + ":" + s + "." + ms;
		if (simple){
			return v + "d " + t;
		}

		if(v>0){
			let d = v %7;
			v -= d;
			v /= 7;
			t = d + "d " + t;
		}
		if (v>0){
			let w = v %4;
			v -= w;
			v /= 4;
			t = w + "w " + t;
		}
		if (v>0){
			let mo = v %12;
			v -= mo;
			v /= 12;
			t = mo + "m " + t;
		}
		if (v>0){
			t = v + "y " + t;
		}
		return t;
	},
	simplify(v){
		// TODO turn this into a for
		// TODO return only one value
		let vv = 1.0/v;
		let t = "/ms";
		if (vv<5){
			vv *= 1000.0;
			t = "/s";
			if (vv<5){
				vv *= 60.0;
				t = "/mi";
				if (vv<5){
					vv *= 60.0;
					t = "/h";
					if (vv<5){
						vv *= 24.0;
						t = "/d";
						if (vv<5){
							vv *= 7;
							t = "/w";
							if (vv<5){
								vv *= 4;
								t = "/mo";
								if (vv<5){
									vv *= 12;
									t = "/y";
								}
							}
						}
					}
				}
			}
		}

		return t + " " + vv;
	},
	show() {
		let sa = _eta.simplify(_eta.a);
		let sl = _eta.simplify(_eta.ld);

		let t = "";
		t += "Progress		: "+ _eta.o +" -"+(_eta.o-_eta.c) +" = "+_eta.c+"<br>";
		t += "ETA			: "+_eta.ms2td(_eta.e) +"<br>";
		t += "Avg. Dur.		: "+_eta.ms2td(_eta.a) +"<br>";
		t += "Last Dur.		: "+_eta.ms2td(_eta.ld) +"<br>";
		t += "Avg. Speed	: "+sa+"<br/>";
		t += "Last Speed	: "+sl+"<br/>";
		t += "--------------------------------------<br/>";
		t += "CalcCurr.			: "+_eta.ms2td(_eta.cs) +"<br>";
		t += "CalcAvg.			: "+_eta.ms2td(_eta.ca) +"<br>";
		t += "CalcE.T.A.		: "+_eta.ms2td(_eta.ce) +"<br>";
		t += "--------------------------------------<br/>";
		t += "Sum			: "+_eta.ms2td(_eta.s) +"<br/>";
		//t += "Start Time	: (" + _eta.st + ")<br/>"+_eta.ms2td(_eta.st) + "<br/>";
		document.getElementById("text").innerHTML = t;
	},
	loadFromUrl() {
		let params = new URLSearchParams(document.location.search.substring(1));
		let c = parseInt(params.get("c"), 10); // start count
		let o = parseInt(params.get("o"), 10); // objective
		let sms = parseInt(params.get("s"), 10); // start ms
		let lms = parseInt(params.get("l"), 10); // last ms
		let toms = parseInt(params.get("toms"), 10); // granularity

		if (isNaN(c) || isNaN(sms) || isNaN(o)) return; // we need this
		if (isNaN(lms)) lms = +new Date(); //gets current milliseconds by default. meh

		document.getElementById("cant").value = o;
		document.getElementById("toms").value = isNaN(toms) ? 1000 : toms;
		document.getElementById("start_count").value = c;
		document.getElementById("start_ms").value = sms;
		document.getElementById("last_ms").value = lms;

		_eta.load();
	},
	saveToUrl() {
		let u = new URL(document.location);
		u.searchParams.set("c", _eta.c); // count 
		u.searchParams.set("o", _eta.o); // objective
		u.searchParams.set("s", _eta.st); // start
		u.searchParams.set("l", _eta.l); // last
		
		window.history.replaceState({}, "E.T.A. " +_eta.ms2td(_eta.e), u);
	}
};

document.addEventListener("DOMContentLoaded", _eta.loadFromUrl);
