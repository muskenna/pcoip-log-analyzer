window.onload = () => {
  let results = document.querySelectorAll("#resultFilter1, #resultFilter2");
  results.forEach((result) => {
    result.addEventListener("mouseover", mouseOver, false);
    result.addEventListener("mouseout", mouseOut, false);

    result.addEventListener("click", (event) => {
      console.log("click");
      document.querySelectorAll("tr").forEach(function (tr) {
        tr.querySelectorAll("td").forEach(function (td) {
          if (td.innerText.match("Passed") || td.innerText.match("Note")) {
            if (tr.classList.contains("hiddenResult")) {
              console.log("remove hiddenResult");
              tr.classList.remove("hiddenResult");
            } else {
              console.log("add hiddenResult");
              tr.classList.add("hiddenResult");
            }
          }
        });
      });
    });
  });

  function mouseOver() {
    let targets = document.querySelectorAll("#resultFilter1, #resultFilter2");
    targets.forEach((target) => {
      target.style.color = "red";
      target.style.cursor = "pointer";
    });
  }

  function mouseOut() {
    let targets = document.querySelectorAll("#resultFilter1, #resultFilter2");
    targets.forEach((target) => {
      target.style.color = "black";
    });
  }
};
