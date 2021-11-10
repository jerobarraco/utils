// Copyright 2015-2021 Jerónimo Barraco Mármol GPL v3

function pad(n, d) {
	return ('0000'+ n).slice(-d); // https://stackoverflow.com/q/10073699/260242
	// yes i'm aware of padStart, but look at this, is so beautifully simple and so much more compatible and less pretentious... (and more cross language)
}

var _eta = {
	to: 1000,//timeout
	c: 0,//count
	st: 0, //start time
	s: 0,//sum (total duration)
	l: 0,//last ms
	ld: 0,//last dur
	a: 0,//avg
	o: 0,//objective
	e: 0,//eta
	sp: 0,//speed
	cd: 0,//current duration
	ca: 0,//current avg
	ce: 0,//current eta
	offset: 0,
	timer: 0,
	BAR_LEN: 24,
	// <progress> is too mainstream (and i also overlooked it >_>')
	// Some bars taken from https://github.com/Changaco/unicode-progress-bars/blob/master/generator.html (but code is mine)
	// 1st char is the empty one, last is the full, the rest (including 1st is middle)
	BARS:[
		"▁▂▃▄▅▆▇█",
		"▁▏▎▍▌▋▋▉█",
		" ▁▂▃▄▅▆▇█",
		" ▏▎▍▌▋▋▉█",
		"░▒▓█",
		"⣀⣄⣤⣦⣶⣷⣿",
		"⣀⣄⣆⣇⣧⣷⣿",
		"□▥▦▨▩▣■",
		"◯⬤",
		"░█",
		"█", // 1 char means that the empty cell is ""
	],
	ClearTimer(){
		clearTimeout(_eta.timer);
		_eta.timer = 0;
	},
	Stop(){
		_eta.ClearTimer();
		_eta.SetCountBtnText("Continue");
		// don't change reset to start, as it actually clicking it will still reset
	},
	Tick(){
		_eta.ClearTimer();
    	// done at the start to avoid adding a delay
		_eta.timer = setTimeout(_eta.Tick, _eta.to);

		let n = +(new Date());
		_eta.cd = n - _eta.l;
		_eta.ca = (_eta.s + _eta.cd)/_eta.c;
		let remaining = (_eta.o -_eta.c -_eta.offset);
		_eta.ce = remaining*_eta.ca;
		_eta.e = (remaining*_eta.a)-_eta.cd;

		_eta.Show();
	},
	TryTick(){
		//// Updates ui, tries to start, stops if reached
		_eta.Tick(); // will do Show properly, as it updates the values.
		_eta.ShowSlow();

		 // notice stop below the tick above
		if(_eta.c >= (_eta.o - _eta.offset))
		 	_eta.Stop(); // stop when target reached
	},
	Count(){
		//start if never started
		if (_eta.st==0){
			_eta.Reset();
			return;
		}

		// restart the timer if its stopped
		if(_eta.timer == 0) {
			_eta.TryTick();
			_eta.SetCountBtnText("Count");
			return;
		}

		// update values
		let n = +(new Date());
		_eta.ld = n - _eta.l;
		_eta.l = n;
		_eta.c += 1;
		// _eta.s += _eta.ld; might be less accurate 
		_eta.s = (_eta.l - _eta.st);// might be more accurate 
		_eta.a = _eta.s/_eta.c;

		_eta.TryTick();

		// on count set load's count value
		document.getElementById("start_count").value = _eta.c;
		// and last ms
		document.getElementById("last_ms").value = _eta.l;
		_eta.SaveToUrl(); // write url
	},
	Restart() {
		// Reset using the document, but not the load part. Sets the rest to initial value.
		_eta.Stop();
		_eta.c = 0;
		_eta.e = 0;//eta
		_eta.s = 0;//sum
		_eta.a = 0;//avg
		_eta.ld = 0;//last_duration
		_eta.sp = 0;//speed
		_eta.cd = 0;//current duration (last dur)
		_eta.ca = 0;//current avg
		_eta.ce = 0;//current eta
		_eta.offset = parseInt(document.getElementById("offset").value);
		_eta.o = parseInt(document.getElementById("cant").value);
		_eta.to = parseInt(document.getElementById("toms").value);
		_eta.l = +new Date(); //last: gets current milliseconds. meh
		_eta.st = _eta.l; //start ms

		_eta.SetTitle(document.getElementById("titles").value)
		_eta.SetCountBtnText("Count");
		document.getElementById("b_reset").value = "Restart";
		// beware conflicts with load
		document.getElementById("start_ms").value = _eta.st;
		document.getElementById("start_count").value = 0; // notice it collides with load
		// not saving to url here because it will mess with load, and reset

		//update ui and start ticking
		_eta.TryTick();
	},
	Reset() {
		// Reset using the document, but not the load part
		_eta.Restart();
		_eta.SaveToUrl();
		_eta.ShowSlow();
	},
	Load() {
		// Loads from document. LoadFromUrl calls this.

		// cache sms and count because "restart" will override it with last (aka now)
		let sms = parseInt(document.getElementById("start_ms").value);
		let c = parseInt(document.getElementById("start_count").value);
		_eta.Restart(); //last is set to now. but we reload it below. It also starts the tick
		// restore original startms
		document.getElementById("start_ms").value = sms;
		_eta.st = sms;
		// load count
		_eta.c = c;
		document.getElementById("start_count").value = c;

		// try to load last ms if possible otherwise "Restart" above makes it default to now
		let nl = parseInt(document.getElementById("last_ms").value);
		if (!isNaN(nl) && nl > 0 && nl > _eta.st) {
			_eta.l = nl;
		}

		_eta.s = (_eta.l - _eta.st);
		_eta.a = _eta.s/_eta.c;
		_eta.ld = _eta.a;

		// update ui
		_eta.SaveToUrl();
		_eta.TryTick();
		_eta.ShowSlow();
	},
	MS2TD(v, simple){
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

		t = pad(h, 2) + ":" + pad(m, 2)+ ":" + pad(s, 2) + "." + pad(ms, 3);
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
	Simplify(v){
		let data = [
			["/ms", 5, 1000],
			["/s", 5, 60],
			["/mi", 5, 60],
			["/h", 5, 24],
			["/d", 5, 7],
			["/w", 5, 4],
			["/mo", 5, 12],
			["/y", Infinity, 1]
		];
		let vv = 1.0/v;
		let t = "";
		for(var i = 0, size = data.length; i < size ; i++) {
			let row = data[i];
			t = row[0];
			if (vv >= row[1]) break;
			vv *= row[2]
		}

		return t + " " + vv;
	},
	CleanBarStyle(bar) {
		return isNaN(bar) || bar < 0 ? 0 : (bar < _eta.BARS.length ? bar : _eta.BARS.length -1);
	},
	GetProgressBar(p) {
		let bari = _eta.CleanBarStyle(parseInt(document.getElementById("bar").value, 10));
		let bar = _eta.BARS[bari];
		let cF = bar[bar.length-1]; // full is at the end
		let cE = bar.length < 2 ? "" : bar[0]; // empty is the first, or empty
		 //include empty as part of partial, looks better, and works better (see 'if' below)
		let cP = bar.length < 2 ? "" : bar.slice(0, -1);

		let len = _eta.BAR_LEN;
		let done = p*len;
		let empty = len - Math.ceil(done);
		let full = Math.floor(done);
		let partial = done - full;

		let b = "";
		b += cF.repeat(full);
		if (partial > 0 && cP.length > 0) { // if theres no partial, theres no empty either, we can skip
			let i = Math.floor(partial * cP.length);
			b += cP[i];
		}
		if (empty>=0) {
			b += cE.repeat(empty);
		}
		return b;
	},
	ShowSlow() {
		let sa = _eta.Simplify(_eta.a);
		let sl = _eta.Simplify(_eta.ld);
		let off_obj = _eta.o - _eta.offset;
		let p = _eta.c/off_obj;

		let t = "";
		t += _eta.GetProgressBar(p) + "<br/>";
		t += "Completion&#9;: "+ (p*100).toFixed(8) + "%<br/>";
		t += "Progress&#9;: "+ _eta.o +" -"+(off_obj-_eta.c) + " -" +_eta.offset + " = " + _eta.c + "<br/>";
   		t += "Last Speed&#9;: "+sl+"<br/>";
		t += "Avg. Speed&#9;: "+sa+"<br/>";
		t += "Last Dur.&#9;: "+_eta.MS2TD(_eta.ld) +"<br/>";
		t += "Avg. Dur.&#9;: "+_eta.MS2TD(_eta.a) +"<br/>";
		t += "Acum.Dur.&#9;: "+_eta.MS2TD(_eta.s) +"<br/>";
		// t += "Start Time	: (" + _eta.st + ")<br/>"+_eta.MS2TD(_eta.st) + "<br/>";
		t += "----------------------------------------";
		//t = t.replace(/	/g, "&#9;"); // works because in the html we have the <pre> tag
		document.getElementById("text_slow").innerHTML = t;
	},
	Show() {
		let t = "";
		t += "ETA&#9;&#9;: "+_eta.MS2TD(_eta.e) +"<br/>";
		t += "CalcE.T.A.&#9;: "+_eta.MS2TD(_eta.ce) +"<br/>";
		t += "CalcLastDur.&#9;: "+_eta.MS2TD(_eta.cd) +"<br/>";
		t += "CalcAvgDur.&#9;: "+_eta.MS2TD(_eta.ca) +"<br/>";
		t += "Est.Dur.&#9;: "+_eta.MS2TD(_eta.e + _eta.s) +"<br/>";
		t += "Est.CalcDur.&#9;: "+_eta.MS2TD(_eta.ce + _eta.s) +"<br/>";
		t += "----------------------------------------<br/>";
		document.getElementById("text").innerHTML = t;
	},
	SetCountBtnText(t) {
		document.getElementById("b_count").value = t;
	},
	SetTitle(nt) {
		document.getElementById("titles").value = nt;
		document.title = "ETA.: " + nt;
	},
	LoadFromUrl() {
		let params = new URLSearchParams(document.location.search.substring(1));
		let c = parseInt(params.get("c"), 10); // start count
		let o = parseInt(params.get("o"), 10); // objective
		let sms = parseInt(params.get("s"), 10); // start ms
		let lms = parseInt(params.get("l"), 10); // last ms
		let toms = parseInt(params.get("to"), 10); // refresh rate
		let bar = parseInt(params.get("b"), 10); // bar style
		let nt = params.get("tt");

		if (isNaN(c) || isNaN(sms) || isNaN(o)) return; // we need this
		if (isNaN(lms)) lms = +new Date(); //gets current milliseconds by default. meh

		document.getElementById("cant").value = o;
		document.getElementById("toms").value = isNaN(toms) ? 1000 : toms;
		document.getElementById("start_count").value = c;
		document.getElementById("start_ms").value = sms;
		document.getElementById("last_ms").value = lms;
		document.getElementById("titles").value = nt;
		document.getElementById("bar").value = _eta.CleanBarStyle(bar);

		// this function should limit itself to set values on the doc elements, load handles the rest
		// this is to support load and reset behaving similar
		_eta.Load();
	},
	SaveToUrl() {
		let u = new URL(document.location);
		u.searchParams.set("c", _eta.c); // count 
		u.searchParams.set("o", _eta.o); // objective
		u.searchParams.set("s", _eta.st); // start
		u.searchParams.set("l", _eta.l); // last
		u.searchParams.set("to", _eta.to) // refresh
		u.searchParams.set("b", document.getElementById("bar").value) // refresh

		u.searchParams.set("tt", document.getElementById("titles").value) // title (last on purpose as it could get long)
		window.history.replaceState({}, "E.T.A. " +_eta.MS2TD(_eta.e), u);
	}
};

document.addEventListener("DOMContentLoaded", _eta.LoadFromUrl);

