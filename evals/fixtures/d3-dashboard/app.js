const data = [
  { day: "Mon", tickets: 48 },
  { day: "Tue", tickets: 61 },
  { day: "Wed", tickets: 57 },
  { day: "Thu", tickets: 72 },
  { day: "Fri", tickets: 39 },
  { day: "Sat", tickets: 12 },
  { day: "Sun", tickets: 9 },
];

const svg = d3.select("#tickets");
const width = +svg.attr("width");
const height = +svg.attr("height");
const margin = { top: 40, right: 20, bottom: 50, left: 60 };
const inner = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`);
const w = width - margin.left - margin.right;
const h = height - margin.top - margin.bottom;

const x = d3.scaleBand().domain(data.map((d) => d.day)).range([0, w]).padding(0.25);
const y = d3.scaleLinear().domain([0, d3.max(data, (d) => d.tickets)]).nice().range([h, 0]);

inner
  .selectAll("rect.bar")
  .data(data)
  .join("rect")
  .attr("class", "bar")
  .attr("x", (d) => x(d.day))
  .attr("y", (d) => y(d.tickets))
  .attr("width", x.bandwidth())
  .attr("height", (d) => h - y(d.tickets));

inner.append("g").attr("class", "axis").attr("transform", `translate(0,${h})`).call(d3.axisBottom(x));
inner.append("g").attr("class", "axis").call(d3.axisLeft(y));

svg.append("text").attr("x", width / 2).attr("y", 24).attr("text-anchor", "middle").style("font-weight", "600").text("Support tickets per weekday");
svg.append("text").attr("x", margin.left + w / 2).attr("y", height - 8).attr("text-anchor", "middle").text("Weekday");
svg.append("text").attr("transform", `rotate(-90)`).attr("x", -(margin.top + h / 2)).attr("y", 16).attr("text-anchor", "middle").text("Tickets opened");
