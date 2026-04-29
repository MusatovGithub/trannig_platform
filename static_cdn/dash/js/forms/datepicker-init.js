jQuery(function ($) {
  $(".mydatepicker, #datepicker, .input-group.date").each(function () {
    $(this).datepicker("destroy"); // Avvalgi `datepicker`ni o‘chiradi
    $(this).datepicker({
      format: "dd.mm.yyyy",
      autoclose: true,
      todayHighlight: false,
    });
  });

  $("#datepicker-autoclose").datepicker("destroy").datepicker({
    format: "dd.mm.yyyy",
    autoclose: true,
    todayHighlight: false
  });

  $("#date-range").datepicker("destroy").datepicker({
    format: "dd.mm.yyyy",
    toggleActive: true
  });

  $("#datepicker-inline").datepicker("destroy").datepicker({
    format: "dd.mm.yyyy",
    todayHighlight: false
  });
});